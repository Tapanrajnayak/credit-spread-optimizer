#!/usr/bin/env python3
"""
Multi-ticker screening example.

Scan multiple tickers and find the best opportunities across all of them.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SpreadType, ScreeningCriteria
from spread_screener import CreditSpreadScreener, create_mock_spread
from spread_optimizer import SpreadOptimizer


def generate_candidates(ticker: str, spot: float, num_spreads: int = 5):
    """Generate candidate spreads for a ticker."""
    candidates = []

    # Generate bull put spreads below spot
    for i in range(num_spreads):
        # Strikes 5%, 10%, 15%, 20%, 25%, 30% below spot
        pct_below = 0.05 * (i + 1)
        short_strike = spot * (1 - pct_below)
        long_strike = short_strike - 5

        spread = create_mock_spread(
            ticker=ticker,
            spread_type=SpreadType.BULL_PUT,
            short_strike=round(short_strike),
            long_strike=round(long_strike),
            short_delta=-0.20 - (i * 0.04),  # Deeper = higher delta (start at 20-delta)
            short_iv=0.28 + (i * 0.01),      # Vary IV
            dte=35
        )

        # Vary characteristics
        spread.iv_percentile = 65 - (i * 3)
        spread.liquidity_score = 2000 - (i * 100)

        candidates.append(spread)

    return candidates


def main():
    print("=" * 70)
    print("MULTI-TICKER CREDIT SPREAD SCAN")
    print("=" * 70)
    print()

    # Define universe of stocks to scan
    universe = {
        "AAPL": 175.0,
        "MSFT": 380.0,
        "GOOGL": 140.0,
        "AMZN": 175.0,
        "TSLA": 250.0,
    }

    print(f"Scanning {len(universe)} tickers: {', '.join(universe.keys())}")
    print()

    # Generate candidates for each ticker
    ticker_candidates = {}
    for ticker, spot in universe.items():
        candidates = generate_candidates(ticker, spot, num_spreads=6)
        ticker_candidates[ticker] = candidates
        print(f"{ticker:6s}: Generated {len(candidates)} candidates (spot: ${spot:.2f})")

    print()

    # Set up screening
    criteria = ScreeningCriteria(
        min_iv_percentile=50.0,
        min_liquidity_score=1000.0,
        max_spread_pct=6.0,
        max_delta=0.50,              # Relaxed for demo
        min_theta=0.05,              # Realistic min theta
        min_probability_profit=0.60,
        min_expected_value=-50.0,    # Relaxed for demo
        min_roc=0.0                  # Relaxed for demo
    )

    screener = CreditSpreadScreener(criteria=criteria)

    # Screen all tickers
    print("Screening all candidates...")
    results = screener.screen_multiple_tickers(ticker_candidates, top_n_per_ticker=2)

    # Summary by ticker
    print("\n" + "=" * 70)
    print("RESULTS BY TICKER")
    print("=" * 70)

    for ticker, result in results.items():
        print(f"\n{ticker}:")
        print(f"  Candidates: {result.total_candidates}")
        print(f"  Passed:     {result.passed_filters} ({result.pass_rate:.1f}%)")

        if result.top_spreads:
            for i, spread in enumerate(result.top_spreads, 1):
                print(f"    {i}. ${spread.short_strike:.0f}/${spread.long_strike:.0f} - "
                      f"Score: {spread.composite_score:.1f}, "
                      f"EV: ${spread.expected_value:.2f}, "
                      f"ROC: {spread.return_on_capital:.1f}%")
        else:
            print(f"    No spreads passed filters")

    # Find best spread across ALL tickers
    all_passing = []
    for result in results.values():
        all_passing.extend(result.top_spreads)

    if all_passing:
        optimizer = SpreadOptimizer()
        best_overall = optimizer.find_best_spread(all_passing)

        print("\n" + "=" * 70)
        print("BEST SPREAD OVERALL")
        print("=" * 70)
        print(f"Ticker:           {best_overall.ticker}")
        print(f"Spread:           {best_overall.description}")
        print(f"Composite Score:  {best_overall.composite_score:.1f}/100")
        print(f"Expected Value:   ${best_overall.expected_value:.2f}")
        print(f"Monthly ROC:      {best_overall.return_on_capital:.1f}%")
        print(f"Prob of Profit:   {best_overall.probability_profit:.1%}")
        print(f"Daily Theta:      ${best_overall.theta:.2f}")
        print()

        # Top 5 overall
        top_5 = optimizer.rank_spreads(all_passing, limit=5)
        print("TOP 5 OPPORTUNITIES:")
        print("-" * 70)
        for i, spread in enumerate(top_5, 1):
            print(f"{i}. {spread.ticker:6s} {spread.description:40s} "
                  f"Score: {spread.composite_score:5.1f} "
                  f"ROC: {spread.return_on_capital:5.1f}%")

        print()

        # Show different rankings
        print("TOP 5 BY EXPECTED VALUE:")
        print("-" * 70)
        by_ev = optimizer.get_top_n_by_metric(all_passing, "expected_value", 5)
        for i, spread in enumerate(by_ev, 1):
            print(f"{i}. {spread.ticker:6s} {spread.description:40s} "
                  f"EV: ${spread.expected_value:6.2f}")

        print()
        print("TOP 5 BY THETA:")
        print("-" * 70)
        by_theta = optimizer.get_top_n_by_metric(all_passing, "theta", 5)
        for i, spread in enumerate(by_theta, 1):
            print(f"{i}. {spread.ticker:6s} {spread.description:40s} "
                  f"Theta: ${spread.theta:5.2f}/day")

    else:
        print("\nNo spreads passed filters across any ticker!")

    print()


if __name__ == "__main__":
    main()
