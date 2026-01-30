#!/usr/bin/env python3
"""
Disciplined credit spread models.

Philosophy: If a rule doesn't reduce tail risk, improve execution,
or increase expected value, it doesn't exist.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RejectionReason(Enum):
    """Why a candidate was rejected (fail-fast)."""
    VIX_TOO_LOW = "IV too low (VIX < 14)"
    ILLIQUID = "Illiquid (volume < 100 or OI < 1000)"
    SLIPPAGE_RISK = "Bid-ask spread too wide (> 5% of credit)"
    BAD_RISK_REWARD = "Risk-reward ratio poor (credit/max_loss < 0.25)"
    IV_PERCENTILE_LOW = "IV percentile < 40 (premium not rich enough)"
    NEGATIVE_EV = "Expected value <= 0 (negative expectancy)"
    DELTA_TOO_HIGH = "Delta exposure too high (abs > 0.20)"
    GAMMA_TOO_HIGH = "Gamma too high near expiry (blow-up risk)"
    THETA_TOO_LOW = "Theta not positive (no income)"


@dataclass(frozen=True)
class CreditSpreadCandidate:
    """
    Immutable credit spread candidate.

    Everything is computed. Nothing is inferred emotionally.
    """
    # Identity
    underlying: str
    expiry: str  # YYYY-MM-DD
    short_strike: float
    long_strike: float

    # Economics
    credit: float  # Per spread (in dollars, not per-contract)
    max_loss: float  # Width - credit

    # Greeks that matter
    delta: float  # Directional risk
    theta: float  # Income (must be > 0)
    gamma: float  # Blow-up detector

    # Risk metrics
    pop: float  # Probability of profit (0-1)
    iv_percentile: float  # 0-100

    # Execution quality
    liquidity_score: float  # Combined volume + OI
    bid_ask_cost: float  # Slippage estimate

    # Truth serum
    ev: float  # Expected value after slippage
    roc: float  # Return on capital (monthly %)

    # Greeks we don't care about (yet)
    vega: float = 0.0  # Track but don't optimize

    # Metadata
    volume: int = 0
    open_interest: int = 0
    dte: int = 0

    @property
    def width(self) -> float:
        """Spread width."""
        return abs(self.short_strike - self.long_strike)

    @property
    def breakeven(self) -> float:
        """Breakeven price."""
        # Assumes bull put spread; adjust for bear call
        return self.short_strike - self.credit

    @property
    def max_profit(self) -> float:
        """Max profit after slippage."""
        return self.credit - self.bid_ask_cost

    @property
    def theta_efficiency(self) -> float:
        """Theta as percentage of capital at risk."""
        if self.max_loss > 0:
            return (self.theta / self.max_loss) * 100
        return 0.0

    @property
    def spread_type(self) -> str:
        """Infer spread type from strikes."""
        if self.long_strike < self.short_strike:
            return "BULL_PUT"
        else:
            return "BEAR_CALL"

    def __str__(self) -> str:
        """Human-readable description."""
        return (
            f"{self.underlying} ${self.short_strike:.0f}/${self.long_strike:.0f} "
            f"{self.spread_type} (DTE: {self.dte})"
        )


@dataclass
class TradeRecommendation:
    """
    Output format for recommended trades.

    If we can't explain it, we don't suggest it.
    """
    candidate: CreditSpreadCandidate
    score: float  # 0-100

    # Must provide
    max_loss: float
    max_profit: float
    breakeven: float
    pop: float
    theta_per_day: float

    # Worst-case scenario
    worst_case_scenario: str

    # Exit plan
    exit_plan: str

    # Why we like it
    rationale: str

    def format_output(self) -> str:
        """Format for display."""
        lines = []
        lines.append("=" * 70)
        lines.append(f"RECOMMENDATION: {self.candidate}")
        lines.append("=" * 70)
        lines.append(f"Score:            {self.score:.1f}/100")
        lines.append("")
        lines.append("ECONOMICS:")
        lines.append(f"  Max Profit:     ${self.max_profit:.2f}")
        lines.append(f"  Max Loss:       ${self.max_loss:.2f}")
        lines.append(f"  Breakeven:      ${self.breakeven:.2f}")
        lines.append(f"  Risk/Reward:    {self.max_loss/self.max_profit:.2f}:1")
        lines.append("")
        lines.append("PROBABILITY:")
        lines.append(f"  P(Profit):      {self.pop:.1%}")
        lines.append(f"  Expected Value: ${self.candidate.ev:.2f}")
        lines.append(f"  ROC (monthly):  {self.candidate.roc:.1f}%")
        lines.append("")
        lines.append("GREEKS:")
        lines.append(f"  Theta/Day:      ${self.theta_per_day:.2f}")
        lines.append(f"  Delta:          {self.candidate.delta:.3f}")
        lines.append(f"  Gamma:          {self.candidate.gamma:.4f}")
        lines.append("")
        lines.append("RISK MANAGEMENT:")
        lines.append(f"  Worst Case:     {self.worst_case_scenario}")
        lines.append(f"  Exit Plan:      {self.exit_plan}")
        lines.append("")
        lines.append("RATIONALE:")
        lines.append(f"  {self.rationale}")
        lines.append("=" * 70)
        return "\n".join(lines)


@dataclass
class HardFilterResult:
    """Result of hard filter evaluation."""
    passed: bool
    rejection_reason: Optional[RejectionReason] = None

    def __bool__(self) -> bool:
        """Allow if result: syntax."""
        return self.passed


@dataclass
class ScreeningConfig:
    """
    Hard-coded configuration.

    These values are NOT to be optimized via backtests.
    Trust logic, not curve fitting.
    """
    # Market filter
    min_vix: float = 14.0

    # Liquidity filter
    min_volume: int = 100
    min_open_interest: int = 1000

    # Execution filter
    max_bid_ask_pct: float = 0.05  # 5% of credit

    # Risk sanity
    min_risk_reward: float = 0.25  # credit/max_loss

    # Strike selection
    target_delta_min: float = 0.15
    target_delta_max: float = 0.20

    # Spread width (boring is good)
    allowed_widths: list = None  # [5] by default

    # IV filter
    min_iv_percentile: float = 40.0
    max_iv_percentile: float = 100.0

    # IV bonus threshold
    iv_bonus_threshold: float = 70.0

    # Greeks sanity
    max_abs_delta: float = 0.20
    max_gamma_near_expiry: float = 0.05
    min_theta: float = 0.01

    # DTE range
    min_dte: int = 20
    max_dte: int = 60

    # Output limit
    max_recommendations: int = 5

    # Scoring weights (DO NOT OPTIMIZE)
    weight_ev: float = 0.35
    weight_iv_percentile: float = 0.25
    weight_theta_efficiency: float = 0.20
    weight_spread_quality: float = 0.10
    weight_roc: float = 0.10

    def __post_init__(self):
        """Set defaults."""
        if self.allowed_widths is None:
            self.allowed_widths = [2,5,7]

    def validate_weights(self) -> bool:
        """Ensure weights sum to 1.0."""
        total = (
            self.weight_ev +
            self.weight_iv_percentile +
            self.weight_theta_efficiency +
            self.weight_spread_quality +
            self.weight_roc
        )
        return abs(total - 1.0) < 0.01
