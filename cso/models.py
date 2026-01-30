#!/usr/bin/env python3
"""
Data models for credit spread optimization.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class SpreadType(Enum):
    """Type of credit spread."""
    BULL_PUT = "bull_put"      # Sell put spread (bullish/neutral)
    BEAR_CALL = "bear_call"    # Sell call spread (bearish/neutral)
    IRON_CONDOR = "iron_condor"  # Sell both sides


class SpreadWidth(Enum):
    """Standard spread widths."""
    NARROW = 5    # 5-point spread
    MEDIUM = 10   # 10-point spread
    WIDE = 15     # 15-point spread


@dataclass
class CreditSpread:
    """
    Represents a credit spread opportunity with all analysis metrics.

    Attributes:
        ticker: Stock symbol
        spread_type: BULL_PUT or BEAR_CALL
        short_strike: Strike of sold option
        long_strike: Strike of bought option (protection)
        credit: Net credit received per spread
        width: Strike width (short - long for puts, long - short for calls)
        dte: Days to expiration

        # Greeks
        delta: Net delta exposure
        theta: Daily theta (positive = collecting)
        gamma: Gamma exposure
        vega: Vega exposure (negative = hurt by IV rise)

        # Quality metrics
        spread_quality_rating: Bid-ask spread quality (excellent/good/acceptable/poor)
        iv_percentile: Current IV percentile (0-100)
        liquidity_score: Combined volume + OI score
        slippage: Estimated total slippage

        # P&L metrics
        max_profit: Maximum profit (= credit - slippage)
        max_loss: Maximum loss (width - credit)
        breakeven: Breakeven price

        # Risk metrics
        probability_profit: Estimated probability of profit
        expected_value: EV = (win_rate * profit) - (loss_rate * loss)
        return_on_capital: ROC as percentage

        # Composite
        composite_score: Overall score (0-100)
    """
    ticker: str
    spread_type: SpreadType
    short_strike: float
    long_strike: float
    credit: float
    width: float
    dte: int

    # Greeks
    delta: float = 0.0
    theta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0

    # Quality
    spread_quality_rating: str = "unknown"
    iv_percentile: float = 0.0
    liquidity_score: float = 0.0
    slippage: float = 0.0

    # P&L
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven: float = 0.0

    # Risk
    probability_profit: float = 0.0
    expected_value: float = 0.0
    return_on_capital: float = 0.0

    # Score
    composite_score: float = 0.0

    # Additional metadata
    short_delta: float = 0.0  # Delta of short leg alone
    long_delta: float = 0.0   # Delta of long leg alone
    short_iv: float = 0.0     # IV of short leg
    long_iv: float = 0.0      # IV of long leg
    skew: float = 0.0         # IV skew (short IV - long IV)

    @property
    def description(self) -> str:
        """Human-readable spread description."""
        if self.spread_type == SpreadType.BULL_PUT:
            return f"{self.ticker} ${self.short_strike:.0f}/${self.long_strike:.0f} Bull Put Spread"
        else:
            return f"{self.ticker} ${self.short_strike:.0f}/${self.long_strike:.0f} Bear Call Spread"

    @property
    def risk_reward_ratio(self) -> float:
        """Risk/reward ratio (lower is better)."""
        if self.max_profit > 0:
            return self.max_loss / self.max_profit
        return float('inf')

    @property
    def theta_efficiency(self) -> float:
        """Theta as percentage of capital at risk."""
        if self.max_loss > 0:
            return (self.theta / self.max_loss) * 100
        return 0.0


@dataclass
class ScreeningCriteria:
    """
    Criteria for screening credit spreads.
    """
    # IV filters
    min_iv_percentile: float = 50.0
    max_iv_percentile: float = 100.0

    # Liquidity filters
    min_liquidity_score: float = 500.0
    min_volume: int = 50
    min_open_interest: int = 500

    # Quality filters
    max_spread_pct: float = 4.0  # Max bid-ask spread %
    min_spread_quality: str = "acceptable"  # excellent/good/acceptable

    # Greeks filters
    max_delta: float = 0.20  # Max absolute delta (for near-neutral)
    min_theta: float = 5.0   # Min daily theta

    # P&L filters
    min_credit: float = 0.20  # Min credit per spread (in $)
    min_probability_profit: float = 0.60
    min_expected_value: float = 0.0
    min_roc: float = 5.0  # Min ROC %

    # Strategy filters
    spread_widths: List[int] = field(default_factory=lambda: [5, 10])
    dte_range: tuple = (30, 45)  # Min/max DTE

    # Delta targeting (for strike selection)
    target_short_delta: float = 0.30  # Sell 30-delta options (~70% win rate)
    delta_tolerance: float = 0.05


@dataclass
class OptimizationWeights:
    """
    Weights for composite scoring.

    All weights should sum to 1.0
    """
    iv_percentile: float = 0.25
    theta_efficiency: float = 0.20
    spread_quality: float = 0.15
    probability_profit: float = 0.15
    expected_value: float = 0.15
    liquidity: float = 0.10

    def validate(self) -> bool:
        """Check if weights sum to 1.0."""
        total = (self.iv_percentile + self.theta_efficiency +
                self.spread_quality + self.probability_profit +
                self.expected_value + self.liquidity)
        return abs(total - 1.0) < 0.01


@dataclass
class ScreeningResult:
    """
    Results from a screening run.
    """
    ticker: str
    total_candidates: int
    passed_filters: int
    top_spreads: List[CreditSpread] = field(default_factory=list)
    filter_stats: dict = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        """Percentage of candidates that passed filters."""
        if self.total_candidates > 0:
            return (self.passed_filters / self.total_candidates) * 100
        return 0.0
