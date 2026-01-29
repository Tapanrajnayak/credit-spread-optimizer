#!/usr/bin/env python3
"""
Tests for filtering functions.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from models import CreditSpread, SpreadType, ScreeningCriteria
from filters import (
    iv_percentile_filter,
    liquidity_filter,
    spread_quality_filter,
    delta_filter,
    theta_filter,
    credit_filter,
    probability_filter,
    expected_value_filter,
    roc_filter,
    dte_filter,
    passes_all_filters,
    get_failed_filters
)


def create_test_spread(**kwargs):
    """Helper to create test spread with defaults."""
    defaults = {
        "ticker": "TEST",
        "spread_type": SpreadType.BULL_PUT,
        "short_strike": 100.0,
        "long_strike": 95.0,
        "credit": 1.50,
        "width": 5.0,
        "dte": 35,
        "delta": 0.10,
        "theta": 10.0,
        "iv_percentile": 60.0,
        "liquidity_score": 1000.0,
        "spread_quality_rating": "good",
        "probability_profit": 0.70,
        "expected_value": 20.0,
        "return_on_capital": 10.0,
    }
    defaults.update(kwargs)
    return CreditSpread(**defaults)


class TestIVPercentileFilter:
    def test_passes_when_in_range(self):
        spread = create_test_spread(iv_percentile=60.0)
        criteria = ScreeningCriteria(min_iv_percentile=50.0, max_iv_percentile=100.0)
        assert iv_percentile_filter(spread, criteria) == True

    def test_fails_when_below_min(self):
        spread = create_test_spread(iv_percentile=40.0)
        criteria = ScreeningCriteria(min_iv_percentile=50.0)
        assert iv_percentile_filter(spread, criteria) == False

    def test_fails_when_above_max(self):
        spread = create_test_spread(iv_percentile=105.0)
        criteria = ScreeningCriteria(max_iv_percentile=100.0)
        assert iv_percentile_filter(spread, criteria) == False


class TestLiquidityFilter:
    def test_passes_when_adequate(self):
        spread = create_test_spread(liquidity_score=1000.0)
        criteria = ScreeningCriteria(min_liquidity_score=500.0)
        assert liquidity_filter(spread, criteria) == True

    def test_fails_when_insufficient(self):
        spread = create_test_spread(liquidity_score=300.0)
        criteria = ScreeningCriteria(min_liquidity_score=500.0)
        assert liquidity_filter(spread, criteria) == False


class TestSpreadQualityFilter:
    def test_excellent_passes_all(self):
        spread = create_test_spread(spread_quality_rating="excellent")
        criteria = ScreeningCriteria(min_spread_quality="acceptable")
        assert spread_quality_filter(spread, criteria) == True

    def test_poor_fails_acceptable(self):
        spread = create_test_spread(spread_quality_rating="poor")
        criteria = ScreeningCriteria(min_spread_quality="acceptable")
        assert spread_quality_filter(spread, criteria) == False

    def test_good_passes_good(self):
        spread = create_test_spread(spread_quality_rating="good")
        criteria = ScreeningCriteria(min_spread_quality="good")
        assert spread_quality_filter(spread, criteria) == True


class TestDeltaFilter:
    def test_passes_when_below_max(self):
        spread = create_test_spread(delta=0.15)
        criteria = ScreeningCriteria(max_delta=0.20)
        assert delta_filter(spread, criteria) == True

    def test_fails_when_above_max(self):
        spread = create_test_spread(delta=0.25)
        criteria = ScreeningCriteria(max_delta=0.20)
        assert delta_filter(spread, criteria) == False

    def test_handles_negative_delta(self):
        spread = create_test_spread(delta=-0.15)
        criteria = ScreeningCriteria(max_delta=0.20)
        assert delta_filter(spread, criteria) == True


class TestThetaFilter:
    def test_passes_when_above_min(self):
        spread = create_test_spread(theta=10.0)
        criteria = ScreeningCriteria(min_theta=5.0)
        assert theta_filter(spread, criteria) == True

    def test_fails_when_below_min(self):
        spread = create_test_spread(theta=3.0)
        criteria = ScreeningCriteria(min_theta=5.0)
        assert theta_filter(spread, criteria) == False


class TestCreditFilter:
    def test_passes_when_above_min(self):
        spread = create_test_spread(credit=1.50)
        criteria = ScreeningCriteria(min_credit=1.00)
        assert credit_filter(spread, criteria) == True

    def test_fails_when_below_min(self):
        spread = create_test_spread(credit=0.50)
        criteria = ScreeningCriteria(min_credit=1.00)
        assert credit_filter(spread, criteria) == False


class TestProbabilityFilter:
    def test_passes_when_above_min(self):
        spread = create_test_spread(probability_profit=0.70)
        criteria = ScreeningCriteria(min_probability_profit=0.60)
        assert probability_filter(spread, criteria) == True

    def test_fails_when_below_min(self):
        spread = create_test_spread(probability_profit=0.50)
        criteria = ScreeningCriteria(min_probability_profit=0.60)
        assert probability_filter(spread, criteria) == False


class TestExpectedValueFilter:
    def test_passes_when_positive(self):
        spread = create_test_spread(expected_value=20.0)
        criteria = ScreeningCriteria(min_expected_value=0.0)
        assert expected_value_filter(spread, criteria) == True

    def test_fails_when_negative(self):
        spread = create_test_spread(expected_value=-10.0)
        criteria = ScreeningCriteria(min_expected_value=0.0)
        assert expected_value_filter(spread, criteria) == False


class TestROCFilter:
    def test_passes_when_above_min(self):
        spread = create_test_spread(return_on_capital=10.0)
        criteria = ScreeningCriteria(min_roc=5.0)
        assert roc_filter(spread, criteria) == True

    def test_fails_when_below_min(self):
        spread = create_test_spread(return_on_capital=3.0)
        criteria = ScreeningCriteria(min_roc=5.0)
        assert roc_filter(spread, criteria) == False


class TestDTEFilter:
    def test_passes_when_in_range(self):
        spread = create_test_spread(dte=35)
        criteria = ScreeningCriteria(dte_range=(30, 45))
        assert dte_filter(spread, criteria) == True

    def test_fails_when_too_short(self):
        spread = create_test_spread(dte=20)
        criteria = ScreeningCriteria(dte_range=(30, 45))
        assert dte_filter(spread, criteria) == False

    def test_fails_when_too_long(self):
        spread = create_test_spread(dte=60)
        criteria = ScreeningCriteria(dte_range=(30, 45))
        assert dte_filter(spread, criteria) == False


class TestCompositeFilters:
    def test_passes_all_filters_when_good_spread(self):
        spread = create_test_spread(
            iv_percentile=60.0,
            liquidity_score=1000.0,
            spread_quality_rating="good",
            delta=0.10,
            theta=10.0,
            credit=1.50,
            probability_profit=0.70,
            expected_value=20.0,
            return_on_capital=10.0,
            dte=35
        )
        criteria = ScreeningCriteria()
        assert passes_all_filters(spread, criteria) == True

    def test_fails_when_one_filter_fails(self):
        spread = create_test_spread(
            iv_percentile=30.0,  # Below 50% minimum
            liquidity_score=1000.0,
            spread_quality_rating="good",
        )
        criteria = ScreeningCriteria(min_iv_percentile=50.0)
        assert passes_all_filters(spread, criteria) == False

    def test_get_failed_filters_returns_correct_list(self):
        spread = create_test_spread(
            iv_percentile=30.0,  # Fails
            liquidity_score=100.0,  # Fails
            theta=2.0,  # Fails
        )
        criteria = ScreeningCriteria(
            min_iv_percentile=50.0,
            min_liquidity_score=500.0,
            min_theta=5.0
        )
        failed = get_failed_filters(spread, criteria)
        assert "iv_percentile" in failed
        assert "liquidity" in failed
        assert "theta" in failed
        assert len([f for f in failed if not f.endswith("_error")]) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
