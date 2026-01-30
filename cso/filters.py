#!/usr/bin/env python3
"""
Individual filter functions for credit spread screening.

Each filter takes a CreditSpread and returns True if it passes the filter.
"""

from .models import CreditSpread, ScreeningCriteria


def iv_percentile_filter(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Filter by IV percentile range."""
    return criteria.min_iv_percentile <= spread.iv_percentile <= criteria.max_iv_percentile


def liquidity_filter(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Filter by liquidity score."""
    return spread.liquidity_score >= criteria.min_liquidity_score


def spread_quality_filter(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Filter by bid-ask spread quality."""
    quality_order = ["excellent", "good", "acceptable", "poor", "avoid"]

    if spread.spread_quality_rating not in quality_order:
        return False

    min_quality = criteria.min_spread_quality
    if min_quality not in quality_order:
        return True

    spread_idx = quality_order.index(spread.spread_quality_rating)
    min_idx = quality_order.index(min_quality)

    return spread_idx <= min_idx


def delta_filter(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Filter by maximum absolute delta (for directional neutrality)."""
    return abs(spread.delta) <= criteria.max_delta


def theta_filter(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Filter by minimum daily theta collection."""
    return spread.theta >= criteria.min_theta


def credit_filter(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Filter by minimum credit received."""
    return spread.credit >= criteria.min_credit


def probability_filter(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Filter by probability of profit."""
    return spread.probability_profit >= criteria.min_probability_profit


def expected_value_filter(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Filter by expected value."""
    return spread.expected_value >= criteria.min_expected_value


def roc_filter(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Filter by return on capital."""
    return spread.return_on_capital >= criteria.min_roc


def dte_filter(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Filter by days to expiration range."""
    min_dte, max_dte = criteria.dte_range
    return min_dte <= spread.dte <= max_dte


# Composite filter function
def apply_all_filters(spread: CreditSpread, criteria: ScreeningCriteria) -> dict:
    """
    Apply all filters and return results.

    Returns:
        dict with filter names and pass/fail status
    """
    filters = {
        "iv_percentile": iv_percentile_filter,
        "liquidity": liquidity_filter,
        "spread_quality": spread_quality_filter,
        "delta": delta_filter,
        "theta": theta_filter,
        "credit": credit_filter,
        "probability": probability_filter,
        "expected_value": expected_value_filter,
        "roc": roc_filter,
        "dte": dte_filter,
    }

    results = {}
    for name, filter_func in filters.items():
        try:
            results[name] = filter_func(spread, criteria)
        except Exception as e:
            results[name] = False
            results[f"{name}_error"] = str(e)

    return results


def passes_all_filters(spread: CreditSpread, criteria: ScreeningCriteria) -> bool:
    """Check if spread passes all filters."""
    results = apply_all_filters(spread, criteria)
    return all(v for k, v in results.items() if not k.endswith("_error"))


def get_failed_filters(spread: CreditSpread, criteria: ScreeningCriteria) -> list:
    """Get list of failed filter names."""
    results = apply_all_filters(spread, criteria)
    return [name for name, passed in results.items()
            if not passed and not name.endswith("_error")]
