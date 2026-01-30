#!/usr/bin/env python3
"""
Credit spread optimizer with composite scoring and ranking.
"""

from typing import List
from .models import CreditSpread, OptimizationWeights


class SpreadOptimizer:
    """
    Ranks credit spreads using multi-factor composite scoring.

    Combines:
    - IV percentile (higher is better for selling premium)
    - Theta efficiency (higher daily income per $ at risk)
    - Spread quality (tighter bid-ask spreads)
    - Probability of profit
    - Expected value
    - Liquidity
    """

    def __init__(self, weights: OptimizationWeights = None):
        """
        Initialize optimizer with scoring weights.

        Args:
            weights: OptimizationWeights object (uses defaults if None)
        """
        self.weights = weights or OptimizationWeights()

        if not self.weights.validate():
            raise ValueError("Optimization weights must sum to 1.0")

    def calculate_composite_score(self, spread: CreditSpread) -> float:
        """
        Calculate composite score for a spread (0-100 scale).

        Each factor is normalized to 0-100 scale and weighted.

        Args:
            spread: CreditSpread to score

        Returns:
            Composite score (0-100, higher is better)
        """
        scores = {}

        # 1. IV Percentile (0-100 already)
        scores['iv'] = spread.iv_percentile

        # 2. Theta Efficiency (normalize: assume 0-2% daily as 0-100)
        theta_eff = spread.theta_efficiency
        scores['theta'] = min(100, (theta_eff / 2.0) * 100)

        # 3. Spread Quality (convert rating to score)
        quality_map = {
            "excellent": 100,
            "good": 75,
            "acceptable": 50,
            "poor": 25,
            "avoid": 0,
            "unknown": 50
        }
        scores['quality'] = quality_map.get(spread.spread_quality_rating, 50)

        # 4. Probability of Profit (0-1 → 0-100)
        scores['prob'] = spread.probability_profit * 100

        # 5. Expected Value (normalize: assume -$100 to +$100 as 0-100)
        # Shift so 0 EV = 50 score
        ev_score = 50 + (spread.expected_value / 2.0)
        scores['ev'] = max(0, min(100, ev_score))

        # 6. Liquidity (normalize: assume 0-5000 as 0-100)
        liquidity_score = min(100, (spread.liquidity_score / 5000) * 100)
        scores['liquidity'] = liquidity_score

        # Calculate weighted composite
        composite = (
            scores['iv'] * self.weights.iv_percentile +
            scores['theta'] * self.weights.theta_efficiency +
            scores['quality'] * self.weights.spread_quality +
            scores['prob'] * self.weights.probability_profit +
            scores['ev'] * self.weights.expected_value +
            scores['liquidity'] * self.weights.liquidity
        )

        return composite

    def rank_spreads(
        self,
        spreads: List[CreditSpread],
        limit: int = None
    ) -> List[CreditSpread]:
        """
        Rank spreads by composite score.

        Args:
            spreads: List of CreditSpread objects
            limit: Return only top N spreads (None = all)

        Returns:
            Sorted list of spreads (highest score first)
        """
        # Calculate scores
        for spread in spreads:
            spread.composite_score = self.calculate_composite_score(spread)

        # Sort by score descending
        ranked = sorted(spreads, key=lambda s: s.composite_score, reverse=True)

        # Apply limit if specified
        if limit is not None:
            ranked = ranked[:limit]

        return ranked

    def find_best_spread(
        self,
        spreads: List[CreditSpread]
    ) -> CreditSpread:
        """
        Find single best spread from list.

        Args:
            spreads: List of CreditSpread objects

        Returns:
            Highest scoring spread
        """
        if not spreads:
            raise ValueError("No spreads provided")

        ranked = self.rank_spreads(spreads, limit=1)
        return ranked[0]

    def compare_spreads(
        self,
        spread1: CreditSpread,
        spread2: CreditSpread
    ) -> dict:
        """
        Detailed comparison between two spreads.

        Args:
            spread1: First spread
            spread2: Second spread

        Returns:
            Dictionary with comparison metrics
        """
        score1 = self.calculate_composite_score(spread1)
        score2 = self.calculate_composite_score(spread2)

        return {
            "spread1": {
                "description": spread1.description,
                "score": score1,
                "ev": spread1.expected_value,
                "roc": spread1.return_on_capital,
                "prob_profit": spread1.probability_profit,
            },
            "spread2": {
                "description": spread2.description,
                "score": score2,
                "ev": spread2.expected_value,
                "roc": spread2.return_on_capital,
                "prob_profit": spread2.probability_profit,
            },
            "winner": "spread1" if score1 > score2 else "spread2",
            "score_difference": abs(score1 - score2)
        }

    def get_top_n_by_metric(
        self,
        spreads: List[CreditSpread],
        metric: str,
        n: int = 5
    ) -> List[CreditSpread]:
        """
        Get top N spreads by specific metric.

        Args:
            spreads: List of spreads
            metric: Attribute name (e.g., "expected_value", "theta", "roc")
            n: Number to return

        Returns:
            Top N spreads sorted by metric
        """
        sorted_spreads = sorted(
            spreads,
            key=lambda s: getattr(s, metric, 0),
            reverse=True
        )
        return sorted_spreads[:n]


class SpreadComparator:
    """Compare different spread configurations."""

    @staticmethod
    def compare_widths(
        narrow_spread: CreditSpread,
        wide_spread: CreditSpread
    ) -> dict:
        """
        Compare narrow vs wide spreads.

        Narrow spreads: Higher win rate, lower premium, less capital
        Wide spreads: Lower win rate, higher premium, more capital
        """
        return {
            "narrow": {
                "description": narrow_spread.description,
                "width": narrow_spread.width,
                "credit": narrow_spread.credit,
                "max_loss": narrow_spread.max_loss,
                "prob_profit": narrow_spread.probability_profit,
                "roc": narrow_spread.return_on_capital,
            },
            "wide": {
                "description": wide_spread.description,
                "width": wide_spread.width,
                "credit": wide_spread.credit,
                "max_loss": wide_spread.max_loss,
                "prob_profit": wide_spread.probability_profit,
                "roc": wide_spread.return_on_capital,
            },
            "analysis": {
                "credit_ratio": wide_spread.credit / narrow_spread.credit if narrow_spread.credit > 0 else 0,
                "risk_ratio": wide_spread.max_loss / narrow_spread.max_loss if narrow_spread.max_loss > 0 else 0,
                "prob_difference": narrow_spread.probability_profit - wide_spread.probability_profit,
            }
        }
