#!/usr/bin/env python3
"""
Disciplined Credit Spread Screener.

Philosophy:
    Your system is not trying to:
        • Predict direction
        • Time tops or bottoms
        • Beat hedge funds

    It is trying to:
        Sell overpriced insurance repeatedly without dying.

That's it.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../python-options-core'))

from typing import List, Optional, Tuple
from dataclasses import dataclass

# Optional yfinance import (only needed for fetching VIX)
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

from disciplined_models import (
    CreditSpreadCandidate,
    TradeRecommendation,
    HardFilterResult,
    RejectionReason,
    ScreeningConfig
)


class DisciplinedScreener:
    """
    Disciplined credit spread screener with fail-fast filters.

    Mental model: We're selling overpriced insurance, not predicting markets.
    """

    def __init__(self, config: Optional[ScreeningConfig] = None):
        """
        Initialize with hard-coded configuration.

        Args:
            config: ScreeningConfig (uses defaults if None)
        """
        self.config = config or ScreeningConfig()

        if not self.config.validate_weights():
            raise ValueError("Scoring weights must sum to 1.0")

        self.rejection_stats = {reason: 0 for reason in RejectionReason}

    # ═══════════════════════════════════════════════════════════════════
    # HARD FILTERS (Fail Fast)
    # ═══════════════════════════════════════════════════════════════════

    def filter_market(self, vix: float) -> HardFilterResult:
        """
        Market filter: Reject if VIX too low.

        Low VIX = cheap premium = not worth the risk.
        """
        if vix < self.config.min_vix:
            return HardFilterResult(False, RejectionReason.VIX_TOO_LOW)
        return HardFilterResult(True)

    def filter_liquidity(self, candidate: CreditSpreadCandidate) -> HardFilterResult:
        """
        Liquidity filter: Reject if illiquid.

        Can't make money if you can't get filled.
        """
        if (candidate.volume < self.config.min_volume or
            candidate.open_interest < self.config.min_open_interest):
            return HardFilterResult(False, RejectionReason.ILLIQUID)
        return HardFilterResult(True)

    def filter_execution(self, candidate: CreditSpreadCandidate) -> HardFilterResult:
        """
        Execution filter: Reject if bid-ask spread too wide.

        Slippage kills edge faster than anything else.
        """
        if candidate.credit > 0:
            bid_ask_pct = candidate.bid_ask_cost / candidate.credit
            if bid_ask_pct > self.config.max_bid_ask_pct:
                return HardFilterResult(False, RejectionReason.SLIPPAGE_RISK)
        return HardFilterResult(True)

    def filter_risk_sanity(self, candidate: CreditSpreadCandidate) -> HardFilterResult:
        """
        Risk sanity filter: Reject if risk/reward is bad.

        If you're risking $4 to make $1, you need >80% win rate.
        That's hard to achieve consistently.
        """
        if candidate.max_loss > 0:
            risk_reward = candidate.credit / candidate.max_loss
            if risk_reward < self.config.min_risk_reward:
                return HardFilterResult(False, RejectionReason.BAD_RISK_REWARD)
        return HardFilterResult(True)

    def filter_iv_percentile(self, candidate: CreditSpreadCandidate) -> HardFilterResult:
        """
        IV filter: Reject if premium not rich enough.

        Selling premium only makes sense when it's overpriced.
        """
        if candidate.iv_percentile < self.config.min_iv_percentile:
            return HardFilterResult(False, RejectionReason.IV_PERCENTILE_LOW)
        return HardFilterResult(True)

    def filter_expected_value(self, candidate: CreditSpreadCandidate) -> HardFilterResult:
        """
        EV filter: This is your truth serum.

        If EV <= 0, you're donating money to market makers.
        """
        if candidate.ev <= 0:
            return HardFilterResult(False, RejectionReason.NEGATIVE_EV)
        return HardFilterResult(True)

    def filter_delta(self, candidate: CreditSpreadCandidate) -> HardFilterResult:
        """
        Delta filter: Keep directional exposure minimal.

        We're selling premium, not making directional bets.
        """
        if abs(candidate.delta) > self.config.max_abs_delta:
            return HardFilterResult(False, RejectionReason.DELTA_TOO_HIGH)
        return HardFilterResult(True)

    def filter_gamma(self, candidate: CreditSpreadCandidate) -> HardFilterResult:
        """
        Gamma filter: Blow-up detector.

        High gamma near expiry = lottery ticket against you.
        """
        if candidate.dte < 7 and candidate.gamma > self.config.max_gamma_near_expiry:
            return HardFilterResult(False, RejectionReason.GAMMA_TOO_HIGH)
        return HardFilterResult(True)

    def filter_theta(self, candidate: CreditSpreadCandidate) -> HardFilterResult:
        """
        Theta filter: Must be collecting theta.

        No positive theta = no income = wrong strategy.
        """
        if candidate.theta <= self.config.min_theta:
            return HardFilterResult(False, RejectionReason.THETA_TOO_LOW)
        return HardFilterResult(True)

    def apply_hard_filters(
        self,
        candidate: CreditSpreadCandidate,
        vix: float
    ) -> HardFilterResult:
        """
        Apply all hard filters in sequence.

        Returns immediately on first failure (fail-fast).
        """
        # Order matters: check cheap filters first
        filters = [
            self.filter_market(vix),
            self.filter_liquidity(candidate),
            self.filter_execution(candidate),
            self.filter_risk_sanity(candidate),
            self.filter_iv_percentile(candidate),
            self.filter_delta(candidate),
            self.filter_gamma(candidate),
            self.filter_theta(candidate),
            self.filter_expected_value(candidate),  # Most expensive, check last
        ]

        for result in filters:
            if not result.passed:
                self.rejection_stats[result.rejection_reason] += 1
                return result

        return HardFilterResult(True)

    # ═══════════════════════════════════════════════════════════════════
    # SCORING (Hard-coded weights)
    # ═══════════════════════════════════════════════════════════════════

    def calculate_score(self, candidate: CreditSpreadCandidate) -> float:
        """
        Calculate composite score (0-100).

        Weights are HARD-CODED. Do not optimize via backtests.
        Trust logic, not curve fitting.

        Weights:
            - EV (35%): Structural edge
            - IV percentile (25%): Premium richness
            - Theta efficiency (20%): Income generation
            - Spread quality (10%): Execution quality
            - ROC (10%): Capital efficiency
        """
        # Normalize each component to 0-100 scale

        # 1. EV score: Assume -$50 to +$50 range -> 0 to 100
        ev_score = max(0, min(100, 50 + candidate.ev))

        # 2. IV percentile: Already 0-100
        iv_score = candidate.iv_percentile

        # Bonus for very high IV (70+)
        if candidate.iv_percentile > self.config.iv_bonus_threshold:
            iv_score = min(100, iv_score * 1.1)

        # 3. Theta efficiency: Assume 0-2% daily -> 0 to 100
        theta_score = min(100, candidate.theta_efficiency * 50)

        # 4. Spread quality: Inverse of bid-ask cost
        # Lower cost = higher score
        # Assume 0-10% cost -> 100 to 0
        spread_quality_pct = (candidate.bid_ask_cost / candidate.credit * 100) if candidate.credit > 0 else 10
        spread_score = max(0, 100 - spread_quality_pct * 10)

        # 5. ROC: Assume 0-20% monthly -> 0 to 100
        roc_score = min(100, candidate.roc * 5)

        # Weighted composite
        composite = (
            ev_score * self.config.weight_ev +
            iv_score * self.config.weight_iv_percentile +
            theta_score * self.config.weight_theta_efficiency +
            spread_score * self.config.weight_spread_quality +
            roc_score * self.config.weight_roc
        )

        return composite

    # ═══════════════════════════════════════════════════════════════════
    # OUTPUT GENERATION (Must explain everything)
    # ═══════════════════════════════════════════════════════════════════

    def create_recommendation(
        self,
        candidate: CreditSpreadCandidate,
        score: float
    ) -> TradeRecommendation:
        """
        Create trade recommendation with full explanation.

        If we can't explain it, we don't suggest it.
        """
        # Worst-case scenario
        worst_case = (
            f"Stock moves beyond ${candidate.breakeven:.2f}. "
            f"Max loss: ${candidate.max_loss:.2f}. "
            f"This occurs in ~{(1-candidate.pop)*100:.0f}% of cases."
        )

        # Exit plan
        if candidate.pop > 0.80:
            exit_plan = (
                f"High probability trade. Hold to expiry if profit > 75%. "
                f"Cut at 2x max profit (${candidate.max_profit * 2:.2f} loss)."
            )
        elif candidate.pop > 0.70:
            exit_plan = (
                f"Standard trade. Take profit at 50% max gain. "
                f"Cut at 2x max profit (${candidate.max_profit * 2:.2f} loss)."
            )
        else:
            exit_plan = (
                f"Moderate probability. Take profit at 30% max gain. "
                f"Cut at 1.5x max profit (${candidate.max_profit * 1.5:.2f} loss)."
            )

        # Rationale
        rationale_parts = []

        if candidate.iv_percentile > 70:
            rationale_parts.append(f"IV at {candidate.iv_percentile:.0f}th percentile (premium rich)")

        if candidate.ev > 10:
            rationale_parts.append(f"Strong positive EV (${candidate.ev:.2f})")

        if candidate.theta_efficiency > 1.0:
            rationale_parts.append(f"Excellent theta efficiency ({candidate.theta_efficiency:.2f}%)")

        if candidate.roc > 10:
            rationale_parts.append(f"High ROC ({candidate.roc:.1f}%/month)")

        if not rationale_parts:
            rationale_parts.append("Meets all minimum criteria for credit spread")

        rationale = "; ".join(rationale_parts)

        return TradeRecommendation(
            candidate=candidate,
            score=score,
            max_loss=candidate.max_loss,
            max_profit=candidate.max_profit,
            breakeven=candidate.breakeven,
            pop=candidate.pop,
            theta_per_day=candidate.theta,
            worst_case_scenario=worst_case,
            exit_plan=exit_plan,
            rationale=rationale
        )

    # ═══════════════════════════════════════════════════════════════════
    # MAIN SCREENING LOGIC
    # ═══════════════════════════════════════════════════════════════════

    def screen(
        self,
        candidates: List[CreditSpreadCandidate],
        vix: float
    ) -> List[TradeRecommendation]:
        """
        Screen candidates and return top recommendations.

        Args:
            candidates: List of credit spread candidates
            vix: Current VIX level

        Returns:
            List of TradeRecommendation (top 3-5 max)
        """
        # Reset rejection stats
        self.rejection_stats = {reason: 0 for reason in RejectionReason}

        # Apply hard filters
        passed_candidates = []
        for candidate in candidates:
            result = self.apply_hard_filters(candidate, vix)
            if result.passed:
                passed_candidates.append(candidate)

        # Score surviving candidates
        scored = []
        for candidate in passed_candidates:
            score = self.calculate_score(candidate)
            scored.append((candidate, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Take top N
        top_n = scored[:self.config.max_recommendations]

        # Create recommendations
        recommendations = [
            self.create_recommendation(candidate, score)
            for candidate, score in top_n
        ]

        return recommendations

    def print_rejection_stats(self):
        """Print filter rejection statistics."""
        print("\n" + "=" * 70)
        print("FILTER REJECTION STATS")
        print("=" * 70)

        total_rejections = sum(self.rejection_stats.values())
        if total_rejections == 0:
            print("No candidates rejected.")
            return

        for reason in RejectionReason:
            count = self.rejection_stats[reason]
            if count > 0:
                pct = (count / total_rejections) * 100
                print(f"{reason.value:50s}: {count:4d} ({pct:5.1f}%)")

        print("=" * 70)

    def screen_and_report(
        self,
        candidates: List[CreditSpreadCandidate],
        vix: float
    ) -> List[TradeRecommendation]:
        """
        Screen candidates and print full report.

        Args:
            candidates: List of credit spread candidates
            vix: Current VIX level

        Returns:
            List of TradeRecommendation
        """
        print(f"\n{'=' * 70}")
        print(f"DISCIPLINED CREDIT SPREAD SCREENER")
        print(f"{'=' * 70}")
        print(f"Total Candidates: {len(candidates)}")
        print(f"Current VIX:      {vix:.2f}")
        print(f"{'=' * 70}\n")

        recommendations = self.screen(candidates, vix)

        print(f"\n{'=' * 70}")
        print(f"SCREENING RESULTS")
        print(f"{'=' * 70}")
        print(f"Candidates Passed Filters: {len(recommendations)}/{len(candidates)}")
        print(f"{'=' * 70}\n")

        # Print rejection stats
        self.print_rejection_stats()

        # Print recommendations
        if recommendations:
            print(f"\n{'=' * 70}")
            print(f"TOP {len(recommendations)} RECOMMENDATIONS")
            print(f"{'=' * 70}\n")

            for i, rec in enumerate(recommendations, 1):
                print(f"\n{'─' * 70}")
                print(f"#{i} - SCORE: {rec.score:.1f}/100")
                print(f"{'─' * 70}")
                print(rec.format_output())
        else:
            print("\n⚠️  NO CANDIDATES PASSED ALL FILTERS")
            print("\nThis is GOOD. Better to wait than force bad trades.")
            print("Discipline means saying NO to most opportunities.\n")

        return recommendations


# ═══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def get_current_vix() -> float:
    """
    Fetch current VIX level from Yahoo Finance.

    Returns:
        Current VIX close price
    """
    if not HAS_YFINANCE:
        print("Warning: yfinance not available. Using default VIX of 15.0")
        print("To fetch live VIX: pip install yfinance")
        return 15.0

    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception as e:
        print(f"Warning: Could not fetch VIX ({e}). Using default 15.0")

    return 15.0  # Default fallback


def calculate_expected_value(
    pop: float,
    max_profit: float,
    max_loss: float,
    slippage: float
) -> float:
    """
    Calculate expected value.

    EV = (POP * profit) - ((1 - POP) * loss) - slippage

    This is your truth serum. If EV <= 0, reject.
    """
    prob_loss = 1.0 - pop
    ev = (pop * max_profit) - (prob_loss * max_loss) - slippage
    return ev


def create_candidate_from_strikes(
    underlying: str,
    expiry: str,
    short_strike: float,
    long_strike: float,
    short_delta: float,
    short_iv: float,
    volume: int,
    open_interest: int,
    dte: int,
    underlying_price: float
) -> CreditSpreadCandidate:
    """
    Create a CreditSpreadCandidate from strike data.

    This would typically be populated from real options data.
    Here we estimate values for demonstration.
    """
    width = abs(short_strike - long_strike)

    # Estimate credit (30-delta option ≈ 1/3 width)
    delta_factor = abs(short_delta) / 0.30  # Normalize to 30-delta
    credit = width * 0.33 * delta_factor

    # Estimate Greeks
    # For bull put spread:
    # - Short put has delta like -0.30 (sell higher strike)
    # - Long put has delta like -0.15 (buy lower strike, further OTM)
    # - Net delta = short_delta - long_delta = -0.30 - (-0.15) = -0.15
    # When we BUY the long put, we subtract its delta (since we're long)
    long_delta_magnitude = abs(short_delta) * 0.5  # Long leg ~50% magnitude
    long_put_delta = -long_delta_magnitude  # Long put still has negative delta

    # Net spread delta (accounting for being SHORT one and LONG the other)
    # Net = short + (-long_put) = short - long_magnitude
    net_delta = short_delta - long_put_delta  # This gives us short + long_magnitude

    theta = width * 0.015  # ~1.5% of width per day
    gamma = 0.02
    vega = -width * 0.1

    # P&L calculations
    bid_ask_cost = credit * 0.05  # Assume 5% slippage
    max_profit = credit - bid_ask_cost
    max_loss = width - credit

    # Probability from delta
    pop = 1.0 - abs(short_delta)

    # EV calculation
    prob_loss = 1.0 - pop
    ev = (pop * max_profit) - (prob_loss * max_loss)

    # ROC (monthly %)
    if max_loss > 0:
        roc = (ev / max_loss) * 100 * (30.0 / dte)
    else:
        roc = 0.0

    # IV percentile (would need historical IV data)
    # For now, estimate based on IV level
    if short_iv > 0.50:
        iv_percentile = 80.0
    elif short_iv > 0.35:
        iv_percentile = 60.0
    elif short_iv > 0.25:
        iv_percentile = 40.0
    else:
        iv_percentile = 20.0

    # Liquidity score
    liquidity_score = volume + (open_interest * 0.5)

    return CreditSpreadCandidate(
        underlying=underlying,
        expiry=expiry,
        short_strike=short_strike,
        long_strike=long_strike,
        credit=credit,
        max_loss=max_loss,
        delta=net_delta,
        theta=theta,
        gamma=gamma,
        pop=pop,
        iv_percentile=iv_percentile,
        liquidity_score=liquidity_score,
        bid_ask_cost=bid_ask_cost,
        ev=ev,
        roc=roc,
        vega=vega,
        volume=volume,
        open_interest=open_interest,
        dte=dte
    )
