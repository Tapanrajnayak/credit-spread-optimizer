#!/usr/bin/env python3
"""
Analysis modules for credit spread evaluation.

Provides functions to calculate:
- IV percentile
- Theta efficiency
- Expected value
- Probability of profit
- Return on capital
"""

from typing import Optional, List
from .models import CreditSpread, SpreadType


class IVAnalyzer:
    """Analyze implied volatility metrics."""

    @staticmethod
    def calculate_iv_percentile(current_iv: float, historical_ivs: List[float]) -> float:
        """
        Calculate IV percentile.

        Args:
            current_iv: Current implied volatility
            historical_ivs: List of historical IV values (e.g., past 252 days)

        Returns:
            Percentile (0-100) where current IV ranks
        """
        if not historical_ivs:
            return 50.0  # Default to median if no data

        count_below = sum(1 for iv in historical_ivs if iv < current_iv)
        percentile = (count_below / len(historical_ivs)) * 100
        return percentile

    @staticmethod
    def is_iv_elevated(iv_percentile: float, threshold: float = 50.0) -> bool:
        """Check if IV is elevated above threshold percentile."""
        return iv_percentile >= threshold


class ThetaAnalyzer:
    """Analyze theta decay metrics."""

    @staticmethod
    def calculate_theta_efficiency(theta: float, capital_at_risk: float) -> float:
        """
        Calculate theta as percentage of capital at risk.

        Higher is better - more daily income per dollar at risk.

        Args:
            theta: Daily theta (positive for credit spreads)
            capital_at_risk: Maximum loss on the spread

        Returns:
            Theta efficiency as percentage
        """
        if capital_at_risk <= 0:
            return 0.0
        return (theta / capital_at_risk) * 100

    @staticmethod
    def annualized_theta_return(theta: float, capital_at_risk: float, dte: int) -> float:
        """
        Calculate annualized return from theta assuming constant decay.

        Args:
            theta: Daily theta
            capital_at_risk: Maximum loss
            dte: Days to expiration

        Returns:
            Annualized return percentage
        """
        if capital_at_risk <= 0 or dte <= 0:
            return 0.0

        total_theta_collection = theta * dte
        return_pct = (total_theta_collection / capital_at_risk) * 100
        annualized = return_pct * (365 / dte)
        return annualized


class ProbabilityAnalyzer:
    """Analyze probability metrics."""

    @staticmethod
    def delta_to_probability(delta: float, option_type: str) -> float:
        """
        Convert delta to approximate probability of expiring ITM.

        For a short put with delta -0.30:
          - Probability ITM ≈ 30%
          - Probability OTM ≈ 70% (this is our win probability)

        Args:
            delta: Option delta
            option_type: "put" or "call"

        Returns:
            Probability of expiring OTM (winning for credit spreads)
        """
        # Delta approximates probability of expiring ITM
        prob_itm = abs(delta)

        # For credit spreads, we win if option expires OTM
        prob_otm = 1.0 - prob_itm

        return prob_otm

    @staticmethod
    def probability_from_short_delta(short_delta: float, spread_type: SpreadType) -> float:
        """
        Calculate probability of profit from short leg delta.

        For bull put spread selling 30-delta put: ~70% win rate
        For bear call spread selling 30-delta call: ~70% win rate
        """
        prob = 1.0 - abs(short_delta)
        return max(0.0, min(1.0, prob))


class ExpectedValueAnalyzer:
    """Calculate expected value metrics."""

    @staticmethod
    def calculate_ev(
        probability_profit: float,
        max_profit: float,
        max_loss: float
    ) -> float:
        """
        Calculate expected value.

        EV = (P(win) × profit) - (P(lose) × loss)

        Args:
            probability_profit: Probability of profit (0-1)
            max_profit: Maximum profit
            max_loss: Maximum loss

        Returns:
            Expected value in dollars
        """
        prob_loss = 1.0 - probability_profit
        ev = (probability_profit * max_profit) - (prob_loss * max_loss)
        return ev

    @staticmethod
    def calculate_roc(
        expected_value: float,
        capital_required: float,
        dte: int
    ) -> float:
        """
        Calculate return on capital as monthly percentage.

        Args:
            expected_value: Expected value in dollars
            capital_required: Capital at risk (max loss)
            dte: Days to expiration

        Returns:
            Monthly ROC as percentage
        """
        if capital_required <= 0 or dte <= 0:
            return 0.0

        # ROC for the trade
        roc = (expected_value / capital_required) * 100

        # Convert to monthly
        monthly_roc = roc * (30 / dte)

        return monthly_roc


class SpreadAnalyzer:
    """Comprehensive spread analysis combining all metrics."""

    def __init__(self):
        self.iv_analyzer = IVAnalyzer()
        self.theta_analyzer = ThetaAnalyzer()
        self.prob_analyzer = ProbabilityAnalyzer()
        self.ev_analyzer = ExpectedValueAnalyzer()

    def analyze_spread(
        self,
        spread: CreditSpread,
        historical_ivs: Optional[List[float]] = None
    ) -> CreditSpread:
        """
        Perform comprehensive analysis on a credit spread.

        Updates the spread object with calculated metrics.

        Args:
            spread: CreditSpread to analyze
            historical_ivs: Historical IV data for percentile calculation

        Returns:
            Updated CreditSpread object
        """
        # IV percentile
        if historical_ivs and spread.short_iv > 0:
            spread.iv_percentile = self.iv_analyzer.calculate_iv_percentile(
                spread.short_iv, historical_ivs
            )

        # Probability of profit
        if spread.short_delta != 0:
            spread.probability_profit = self.prob_analyzer.probability_from_short_delta(
                spread.short_delta, spread.spread_type
            )

        # Expected value
        spread.expected_value = self.ev_analyzer.calculate_ev(
            spread.probability_profit,
            spread.max_profit,
            spread.max_loss
        )

        # Return on capital (monthly)
        spread.return_on_capital = self.ev_analyzer.calculate_roc(
            spread.expected_value,
            spread.max_loss,
            spread.dte
        )

        return spread


def calculate_margin_requirement(width: float, contracts: int = 1) -> float:
    """
    Calculate margin requirement for credit spread.

    For credit spreads, margin = width of spread × 100 × contracts

    Args:
        width: Strike width
        contracts: Number of contracts

    Returns:
        Margin requirement in dollars
    """
    return width * 100 * contracts
