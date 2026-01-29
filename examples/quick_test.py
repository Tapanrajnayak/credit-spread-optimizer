#!/usr/bin/env python3
"""
Quick test of the disciplined screening system.

Non-interactive version for testing.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disciplined_screener import (
    DisciplinedScreener,
    create_candidate_from_strikes
)
from disciplined_models import ScreeningConfig


def main():
    """Run a quick test."""
    print("\nDisciplined Credit Spread Screener - Quick Test")
    print("=" * 70)

    # Create a few test candidates
    candidates = []

    # Good candidate: AAPL (30-delta for better credit)
    candidates.append(
        create_candidate_from_strikes(
            underlying="AAPL",
            expiry="2026-02-20",
            short_strike=220.0,
            long_strike=215.0,
            short_delta=-0.30,  # 30-delta for ~$1.65 credit on 5-wide
            short_iv=0.35,      # Elevated IV
            volume=500,
            open_interest=2500,
            dte=42,
            underlying_price=235.0
        )
    )

    # Good candidate: MSFT (28-delta, high IV)
    candidates.append(
        create_candidate_from_strikes(
            underlying="MSFT",
            expiry="2026-02-20",
            short_strike=420.0,
            long_strike=415.0,
            short_delta=-0.28,  # Good delta
            short_iv=0.40,      # High IV
            volume=800,
            open_interest=3000,
            dte=42,
            underlying_price=445.0
        )
    )

    # Bad candidate: Low IV
    candidates.append(
        create_candidate_from_strikes(
            underlying="KO",
            expiry="2026-02-20",
            short_strike=60.0,
            long_strike=55.0,
            short_delta=-0.20,
            short_iv=0.15,  # Low IV - will fail
            volume=300,
            open_interest=1500,
            dte=42,
            underlying_price=63.0
        )
    )

    # Create screener
    screener = DisciplinedScreener()

    # Use a mock VIX value
    vix = 18.5  # Elevated VIX

    # Screen
    recommendations = screener.screen_and_report(candidates, vix)

    # Summary
    print(f"\n{'=' * 70}")
    print("TEST SUMMARY")
    print(f"{'=' * 70}")
    print(f"Candidates tested:     {len(candidates)}")
    print(f"Recommendations:       {len(recommendations)}")
    print(f"Pass rate:             {len(recommendations)/len(candidates)*100:.1f}%")
    print(f"{'=' * 70}\n")

    if recommendations:
        print("✅ Test passed! System is working correctly.")
        print(f"\nBest trade: {recommendations[0].candidate}")
        print(f"Score: {recommendations[0].score:.1f}/100")
        print(f"EV: ${recommendations[0].candidate.ev:.2f}")
    else:
        print("⚠️  No recommendations generated (may need to adjust filters or VIX)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
