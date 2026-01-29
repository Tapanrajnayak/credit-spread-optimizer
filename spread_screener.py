#!/usr/bin/env python3
"""
Main credit spread screening engine.

Provides high-level interface for screening and finding optimal credit spreads.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../python-options-core'))

from typing import List, Optional
from models import (
    CreditSpread, SpreadType, ScreeningCriteria,
    ScreeningResult, OptimizationWeights
)
from filters import passes_all_filters, get_failed_filters
from analyzers import SpreadAnalyzer
from spread_optimizer import SpreadOptimizer


class CreditSpreadScreener:
    """
    Main screening engine for credit spreads.

    Workflow:
    1. Generate candidate spreads for a ticker
    2. Apply filters (IV, liquidity, quality, etc.)
    3. Analyze passing spreads (Greeks, EV, ROC)
    4. Rank by composite score
    """

    def __init__(
        self,
        criteria: Optional[ScreeningCriteria] = None,
        weights: Optional[OptimizationWeights] = None
    ):
        """
        Initialize screener.

        Args:
            criteria: ScreeningCriteria object (uses defaults if None)
            weights: OptimizationWeights for ranking (uses defaults if None)
        """
        self.criteria = criteria or ScreeningCriteria()
        self.analyzer = SpreadAnalyzer()
        self.optimizer = SpreadOptimizer(weights)

    def screen(
        self,
        candidates: List[CreditSpread],
        analyze: bool = True,
        rank: bool = True
    ) -> ScreeningResult:
        """
        Screen a list of candidate spreads.

        Args:
            candidates: List of CreditSpread objects to evaluate
            analyze: Run full analysis on passing spreads
            rank: Rank results by composite score

        Returns:
            ScreeningResult with filtered and ranked spreads
        """
        total = len(candidates)
        passed = []
        filter_stats = {
            "total": total,
            "passed": 0,
            "failed_by_filter": {}
        }

        # Apply filters
        for spread in candidates:
            if passes_all_filters(spread, self.criteria):
                passed.append(spread)
            else:
                # Track which filters failed
                failed = get_failed_filters(spread, self.criteria)
                for filter_name in failed:
                    filter_stats["failed_by_filter"][filter_name] = \
                        filter_stats["failed_by_filter"].get(filter_name, 0) + 1

        filter_stats["passed"] = len(passed)

        # Analyze passing spreads
        if analyze:
            for spread in passed:
                self.analyzer.analyze_spread(spread)

        # Rank by composite score
        if rank and passed:
            passed = self.optimizer.rank_spreads(passed)

        # Build result
        result = ScreeningResult(
            ticker=candidates[0].ticker if candidates else "",
            total_candidates=total,
            passed_filters=len(passed),
            top_spreads=passed,
            filter_stats=filter_stats
        )

        return result

    def find_best_spread(
        self,
        candidates: List[CreditSpread]
    ) -> Optional[CreditSpread]:
        """
        Find single best spread from candidates.

        Args:
            candidates: List of CreditSpread objects

        Returns:
            Best spread or None if no spreads pass filters
        """
        result = self.screen(candidates, analyze=True, rank=True)

        if result.top_spreads:
            return result.top_spreads[0]
        return None

    def screen_multiple_tickers(
        self,
        ticker_candidates: dict,
        top_n_per_ticker: int = 3
    ) -> dict:
        """
        Screen multiple tickers and return top spreads for each.

        Args:
            ticker_candidates: Dict mapping ticker -> list of CreditSpread
            top_n_per_ticker: Number of top spreads to return per ticker

        Returns:
            Dict mapping ticker -> ScreeningResult
        """
        results = {}

        for ticker, candidates in ticker_candidates.items():
            result = self.screen(candidates, analyze=True, rank=True)
            # Limit to top N
            result.top_spreads = result.top_spreads[:top_n_per_ticker]
            results[ticker] = result

        return results

    def get_screening_summary(self, result: ScreeningResult) -> str:
        """
        Generate human-readable screening summary.

        Args:
            result: ScreeningResult to summarize

        Returns:
            Formatted summary string
        """
        lines = []
        lines.append(f"=" * 70)
        lines.append(f"SCREENING SUMMARY: {result.ticker}")
        lines.append(f"=" * 70)
        lines.append(f"Total Candidates: {result.total_candidates}")
        lines.append(f"Passed Filters:   {result.passed_filters} ({result.pass_rate:.1f}%)")
        lines.append("")

        if result.filter_stats.get("failed_by_filter"):
            lines.append("Failed by Filter:")
            for filter_name, count in sorted(
                result.filter_stats["failed_by_filter"].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                lines.append(f"  {filter_name:20s}: {count:3d} spreads")
            lines.append("")

        if result.top_spreads:
            lines.append(f"Top {len(result.top_spreads)} Spreads:")
            lines.append("-" * 70)
            for i, spread in enumerate(result.top_spreads[:5], 1):
                lines.append(f"{i}. {spread.description}")
                lines.append(f"   Score: {spread.composite_score:.1f} | "
                           f"EV: ${spread.expected_value:.2f} | "
                           f"ROC: {spread.return_on_capital:.1f}% | "
                           f"P(profit): {spread.probability_profit:.0%}")
                lines.append(f"   Credit: ${spread.credit:.2f} | "
                           f"Max Loss: ${spread.max_loss:.2f} | "
                           f"Theta: ${spread.theta:.2f}/day")
                lines.append("")
        else:
            lines.append("No spreads passed all filters.")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


def create_mock_spread(
    ticker: str,
    spread_type: SpreadType,
    short_strike: float,
    long_strike: float,
    short_delta: float = -0.30,
    short_iv: float = 0.30,
    dte: int = 35
) -> CreditSpread:
    """
    Create a mock CreditSpread for testing.

    Estimates credit, Greeks, and other metrics based on typical values.

    Args:
        ticker: Stock symbol
        spread_type: BULL_PUT or BEAR_CALL
        short_strike: Strike of sold option
        long_strike: Strike of bought option
        short_delta: Delta of short leg
        short_iv: IV of short leg
        dte: Days to expiration

    Returns:
        CreditSpread with estimated values
    """
    width = abs(short_strike - long_strike)

    # Estimate credit (rough approximation)
    # For 30-delta option, credit ≈ 1/3 of width
    credit = width * 0.33

    # Estimate long leg delta (typically ~10-15 delta for protection)
    long_delta = short_delta * 0.5

    # Net delta
    net_delta = short_delta + long_delta

    # Estimate theta (rough: ~1-2% of width per day)
    theta = width * 0.015

    # Gamma (smaller for credit spreads)
    gamma = 0.02

    # Vega (negative for short premium)
    vega = -width * 0.1

    # P&L
    slippage = credit * 0.1
    max_profit = (credit * 100) - slippage  # Per contract
    max_loss = (width * 100) - (credit * 100)

    # Probability of profit (from short delta)
    # If selling 30-delta put, ~70% chance of expiring OTM
    probability_profit = 1.0 - abs(short_delta)

    # Expected value
    prob_loss = 1.0 - probability_profit
    expected_value = (probability_profit * max_profit) - (prob_loss * max_loss)

    # Return on capital (monthly %)
    roc = (expected_value / max_loss) * 100 * (30 / dte) if max_loss > 0 else 0.0

    # Breakeven
    if spread_type == SpreadType.BULL_PUT:
        breakeven = short_strike - credit
    else:
        breakeven = short_strike + credit

    spread = CreditSpread(
        ticker=ticker,
        spread_type=spread_type,
        short_strike=short_strike,
        long_strike=long_strike,
        credit=credit,
        width=width,
        dte=dte,
        delta=net_delta,
        theta=theta,
        gamma=gamma,
        vega=vega,
        spread_quality_rating="good",
        iv_percentile=65.0,
        liquidity_score=1500.0,
        slippage=slippage,
        max_profit=max_profit,
        max_loss=max_loss,
        breakeven=breakeven,
        probability_profit=probability_profit,
        expected_value=expected_value,
        return_on_capital=roc,
        short_delta=short_delta,
        long_delta=long_delta,
        short_iv=short_iv,
        long_iv=short_iv * 0.95,
        skew=short_iv * 0.05
    )

    return spread
