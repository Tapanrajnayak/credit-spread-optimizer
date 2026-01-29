#!/usr/bin/env python3
"""
Tests for spread optimizer and ranking.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from models import CreditSpread, SpreadType, OptimizationWeights
from spread_optimizer import SpreadOptimizer, SpreadComparator


def create_test_spread(**kwargs):
    """Helper to create test spread."""
    defaults = {
        "ticker": "TEST",
        "spread_type": SpreadType.BULL_PUT,
        "short_strike": 100.0,
        "long_strike": 95.0,
        "credit": 1.50,
        "width": 5.0,
        "dte": 35,
        "theta": 10.0,
        "iv_percentile": 60.0,
        "liquidity_score": 1000.0,
        "spread_quality_rating": "good",
        "probability_profit": 0.70,
        "expected_value": 20.0,
        "return_on_capital": 10.0,
        "theta_efficiency": 2.0,
        "max_profit": 140.0,
        "max_loss": 360.0,
    }
    defaults.update(kwargs)
    return CreditSpread(**defaults)


class TestOptimizationWeights:
    def test_default_weights_sum_to_one(self):
        weights = OptimizationWeights()
        assert weights.validate() == True

    def test_custom_weights_validation(self):
        weights = OptimizationWeights(
            iv_percentile=0.30,
            theta_efficiency=0.30,
            spread_quality=0.10,
            probability_profit=0.10,
            expected_value=0.10,
            liquidity=0.10
        )
        assert weights.validate() == True

    def test_invalid_weights_fail_validation(self):
        weights = OptimizationWeights(
            iv_percentile=0.50,
            theta_efficiency=0.50,
            spread_quality=0.50,
            probability_profit=0.50,
            expected_value=0.50,
            liquidity=0.50
        )
        assert weights.validate() == False


class TestSpreadOptimizer:
    def test_calculate_composite_score(self):
        spread = create_test_spread(
            iv_percentile=80.0,
            theta_efficiency=1.5,
            spread_quality_rating="excellent",
            probability_profit=0.75,
            expected_value=30.0,
            liquidity_score=2000.0
        )

        optimizer = SpreadOptimizer()
        score = optimizer.calculate_composite_score(spread)

        assert 0 <= score <= 100
        assert score > 50  # This should be a good spread

    def test_rank_spreads_orders_correctly(self):
        # Create spreads with varying quality
        spread1 = create_test_spread(
            ticker="GOOD",
            iv_percentile=80.0,
            probability_profit=0.80,
            expected_value=40.0
        )

        spread2 = create_test_spread(
            ticker="BETTER",
            iv_percentile=90.0,
            probability_profit=0.85,
            expected_value=50.0
        )

        spread3 = create_test_spread(
            ticker="POOR",
            iv_percentile=40.0,
            probability_profit=0.55,
            expected_value=5.0
        )

        optimizer = SpreadOptimizer()
        ranked = optimizer.rank_spreads([spread1, spread2, spread3])

        # BETTER should rank highest
        assert ranked[0].ticker == "BETTER"
        assert ranked[-1].ticker == "POOR"

    def test_rank_spreads_with_limit(self):
        spreads = [create_test_spread(ticker=f"TEST{i}") for i in range(10)]
        optimizer = SpreadOptimizer()
        ranked = optimizer.rank_spreads(spreads, limit=3)

        assert len(ranked) == 3

    def test_find_best_spread(self):
        spreads = [
            create_test_spread(ticker="A", expected_value=10.0),
            create_test_spread(ticker="B", expected_value=50.0),
            create_test_spread(ticker="C", expected_value=30.0),
        ]

        optimizer = SpreadOptimizer()
        best = optimizer.find_best_spread(spreads)

        # Should pick B with highest EV (among other factors)
        assert best.ticker == "B"

    def test_find_best_spread_raises_on_empty_list(self):
        optimizer = SpreadOptimizer()
        with pytest.raises(ValueError):
            optimizer.find_best_spread([])

    def test_compare_spreads(self):
        spread1 = create_test_spread(
            ticker="AAPL",
            expected_value=30.0,
            probability_profit=0.70
        )

        spread2 = create_test_spread(
            ticker="MSFT",
            expected_value=40.0,
            probability_profit=0.75
        )

        optimizer = SpreadOptimizer()
        comparison = optimizer.compare_spreads(spread1, spread2)

        assert "spread1" in comparison
        assert "spread2" in comparison
        assert "winner" in comparison
        assert comparison["winner"] in ["spread1", "spread2"]

    def test_get_top_n_by_metric(self):
        spreads = [
            create_test_spread(ticker="A", theta=5.0),
            create_test_spread(ticker="B", theta=15.0),
            create_test_spread(ticker="C", theta=10.0),
        ]

        optimizer = SpreadOptimizer()
        top_theta = optimizer.get_top_n_by_metric(spreads, "theta", n=2)

        assert len(top_theta) == 2
        assert top_theta[0].ticker == "B"  # Highest theta
        assert top_theta[1].ticker == "C"  # Second highest


class TestSpreadComparator:
    def test_compare_widths(self):
        narrow = create_test_spread(
            width=5.0,
            credit=1.50,
            max_loss=350.0,
            probability_profit=0.75,
            return_on_capital=12.0
        )

        wide = create_test_spread(
            width=10.0,
            credit=3.00,
            max_loss=700.0,
            probability_profit=0.65,
            return_on_capital=10.0
        )

        comparison = SpreadComparator.compare_widths(narrow, wide)

        assert "narrow" in comparison
        assert "wide" in comparison
        assert "analysis" in comparison
        assert comparison["analysis"]["credit_ratio"] > 1.0  # Wide has more credit
        assert comparison["analysis"]["prob_difference"] > 0  # Narrow has higher prob


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
