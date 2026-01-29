#!/usr/bin/env python3
"""
Basic credit spread screening example.

Demonstrates:
1. Creating candidate spreads
2. Applying filters
3. Ranking by composite score
4. Analyzing results
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SpreadType, ScreeningCriteria, OptimizationWeights
from spread_screener import CreditSpreadScreener, create_mock_spread


def main():
    print("=" * 70)
    print("CREDIT SPREAD SCREENING - Basic Example")
    print("=" * 70)
    print()

    # Create candidate spreads for AAPL
    # Stock at $175, looking at bull put spreads
    candidates = []

    # Generate spreads at different strikes with 5-point width
    strikes = [160, 165, 170, 175, 180]
    for short_strike in strikes:
        long_strike = short_strike - 5

        # Create spread with varying characteristics
        spread = create_mock_spread(
            ticker="AAPL",
            spread_type=SpreadType.BULL_PUT,
            short_strike=short_strike,
            long_strike=long_strike,
            short_delta=-0.30,  # Targeting 70% win rate
            short_iv=0.28,
            dte=35
        )

        # Vary IV percentile to simulate different opportunities
        spread.iv_percentile = 50 + (short_strike - 165) * 5

        # Vary liquidity
        spread.liquidity_score = 1000 + (short_strike - 160) * 100

        candidates.append(spread)

    # Also try 10-point width spreads
    for short_strike in [165, 170]:
        long_strike = short_strike - 10

        spread = create_mock_spread(
            ticker="AAPL",
            spread_type=SpreadType.BULL_PUT,
            short_strike=short_strike,
            long_strike=long_strike,
            short_delta=-0.30,
            short_iv=0.28,
            dte=35
        )

        spread.iv_percentile = 55
        spread.liquidity_score = 1200
        spread.credit = spread.width * 0.4  # Wider spreads get more credit

        candidates.append(spread)

    print(f"Generated {len(candidates)} candidate spreads")
    print()

    # Set up screening criteria
    criteria = ScreeningCriteria(
        min_iv_percentile=50.0,      # Only trade when IV is elevated
        min_liquidity_score=800.0,   # Require decent liquidity
        max_spread_pct=6.0,          # Acceptable bid-ask spreads
        min_spread_quality="acceptable",
        max_delta=0.50,              # Directional exposure (relaxed for testing)
        min_theta=0.05,              # Minimum daily theta
        min_probability_profit=0.60, # At least 60% win rate
        min_expected_value=-50.0,    # Allow slightly negative EV for demo
        min_roc=0.0,                 # Relaxed for demo
        dte_range=(30, 45)           # 30-45 DTE sweet spot
    )

    # Set up optimization weights
    weights = OptimizationWeights(
        iv_percentile=0.25,
        theta_efficiency=0.20,
        spread_quality=0.15,
        probability_profit=0.15,
        expected_value=0.15,
        liquidity=0.10
    )

    # Create screener
    screener = CreditSpreadScreener(criteria=criteria, weights=weights)

    # Screen spreads
    print("Screening spreads...")
    result = screener.screen(candidates, analyze=True, rank=True)

    # Print summary
    print(screener.get_screening_summary(result))

    # Detailed look at top spread
    if result.top_spreads:
        print("\n" + "=" * 70)
        print("TOP SPREAD DETAILS")
        print("=" * 70)
        best = result.top_spreads[0]

        print(f"Ticker:           {best.ticker}")
        print(f"Strategy:         {best.description}")
        print(f"Strikes:          ${best.short_strike:.0f} / ${best.long_strike:.0f}")
        print(f"Width:            ${best.width:.0f}")
        print(f"DTE:              {best.dte}")
        print()

        print(f"PREMIUM & P/L")
        print(f"  Credit:         ${best.credit:.2f} per spread")
        print(f"  Max Profit:     ${best.max_profit:.2f}")
        print(f"  Max Loss:       ${best.max_loss:.2f}")
        print(f"  Breakeven:      ${best.breakeven:.2f}")
        print(f"  Risk/Reward:    {best.risk_reward_ratio:.2f}")
        print()

        print(f"GREEKS")
        print(f"  Delta:          {best.delta:.3f}")
        print(f"  Theta:          ${best.theta:.2f}/day")
        print(f"  Gamma:          {best.gamma:.3f}")
        print(f"  Vega:           {best.vega:.2f}")
        print()

        print(f"QUALITY METRICS")
        print(f"  Spread Quality: {best.spread_quality_rating.upper()}")
        print(f"  IV Percentile:  {best.iv_percentile:.1f}")
        print(f"  Liquidity:      {best.liquidity_score:.0f}")
        print()

        print(f"PERFORMANCE")
        print(f"  Prob of Profit: {best.probability_profit:.1%}")
        print(f"  Expected Value: ${best.expected_value:.2f}")
        print(f"  Monthly ROC:    {best.return_on_capital:.1f}%")
        print(f"  Composite Score: {best.composite_score:.1f}/100")
        print()

        print(f"RECOMMENDATION")
        print(f"  ✓ This spread passes all filters and ranks highest")
        print(f"  ✓ {best.probability_profit:.0%} probability of profit")
        print(f"  ✓ ${best.theta:.2f}/day theta collection")
        print(f"  ✓ {best.return_on_capital:.1f}% monthly ROC")
        print()


if __name__ == "__main__":
    main()
