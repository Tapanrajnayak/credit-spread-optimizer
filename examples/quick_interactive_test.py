#!/usr/bin/env python3
"""
Quick non-interactive test of the interactive screener.
Pre-loads inputs for demonstration.
"""

import sys

from cso.disciplined_screener import DisciplinedScreener, get_current_vix
from cso.disciplined_models import ScreeningConfig

# Import the functions from the demo
from examples.disciplined_screening_demo import (
    generate_candidates_for_ticker,
    print_banner
)


def main():
    """Run a quick test with pre-set tickers."""
    print_banner()

    # Pre-set inputs
    tickers = ['AAPL', 'MSFT', 'TSLA']
    mode = 'conservative'

    print(f"Testing with tickers: {', '.join(tickers)}")
    print(f"Mode: {mode.upper()}")
    print("─" * 70)

    # Create config
    config = ScreeningConfig()  # Conservative
    screener = DisciplinedScreener(config)

    # Get VIX
    print("\n📊 Fetching market data...")
    vix = get_current_vix()
    print(f"   Current VIX: {vix:.2f}")

    # Generate candidates
    print("\n🔍 Generating option candidates...")
    all_candidates = []

    for ticker in tickers:
        print(f"\n  {ticker}:")
        ticker_candidates = generate_candidates_for_ticker(ticker)
        print(f"    Generated {len(ticker_candidates)} spread candidates")
        all_candidates.extend(ticker_candidates)

    print(f"\n✓ Total candidates across all tickers: {len(all_candidates)}")

    # Screen
    print("\n" + "=" * 70)
    print("⚡ APPLYING HARD FILTERS")
    print("=" * 70)

    recommendations = screener.screen(all_candidates, vix)

    # Print rejection stats
    screener.print_rejection_stats()

    # Results
    print("\n" + "=" * 70)
    print("📋 RESULTS")
    print("=" * 70)
    print(f"Total candidates:      {len(all_candidates)}")
    print(f"Passed all filters:    {len(recommendations)}")
    if all_candidates:
        print(f"Pass rate:             {len(recommendations)/len(all_candidates)*100:.1f}%")
    print("=" * 70)

    if not recommendations:
        print("\n❌ NO OPPORTUNITIES FOUND")
        print("\nThis is GOOD. Discipline means saying NO to most opportunities.")
        return 0

    # Show top recommendation
    print("\n" + "=" * 70)
    print("🏆 TOP RECOMMENDATION")
    print("=" * 70)

    best = recommendations[0]
    print(best.format_output())

    # Show runner-ups
    if len(recommendations) > 1:
        print("\n" + "=" * 70)
        print(f"📊 RUNNER-UPS (Top {min(5, len(recommendations)-1)})")
        print("=" * 70)

        for i, rec in enumerate(recommendations[1:6], 2):
            print(f"\n#{i} - {rec.candidate} - Score: {rec.score:.1f}/100")
            print(f"     EV: ${rec.candidate.ev:.2f} | "
                  f"POP: {rec.candidate.pop:.0%} | "
                  f"ROC: {rec.candidate.roc:.1f}%/mo | "
                  f"Theta: ${rec.candidate.theta:.2f}/day")

    # Summary
    print("\n" + "=" * 70)
    print("📝 SUMMARY")
    print("=" * 70)
    print(f"\n✓ Screened {len(tickers)} ticker(s): {', '.join(tickers)}")
    print(f"✓ Evaluated {len(all_candidates)} possible spreads")
    print(f"✓ Found {len(recommendations)} tradeable opportunit{'y' if len(recommendations)==1 else 'ies'}")
    if all_candidates:
        print(f"✓ Rejection rate: {(1 - len(recommendations)/len(all_candidates))*100:.1f}%")
    print(f"\n🎯 Best Trade: {best.candidate}")
    print(f"   Score: {best.score:.1f}/100 | EV: ${best.candidate.ev:.2f} | ROC: {best.candidate.roc:.1f}%/mo")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
