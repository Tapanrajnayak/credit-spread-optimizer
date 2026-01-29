#!/usr/bin/env python3
"""
Disciplined Credit Spread Screener (Command-Line Interface).

Screen ticker(s) for credit spread opportunities and pick the best trade.

Philosophy:
    We're selling overpriced insurance repeatedly without dying.
    That's it.
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disciplined_screener import (
    DisciplinedScreener,
    create_candidate_from_strikes,
    get_current_vix,
    HAS_YFINANCE
)
from disciplined_models import ScreeningConfig

# Optional yfinance for fetching current prices
if HAS_YFINANCE:
    import yfinance as yf


def get_stock_price(ticker: str) -> float:
    """
    Get current stock price.

    Args:
        ticker: Stock symbol

    Returns:
        Current price or None if unavailable
    """
    if not HAS_YFINANCE:
        return None

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception as e:
        print(f"  Warning: Could not fetch price for {ticker}: {e}")

    return None


def estimate_iv_percentile(ticker: str) -> float:
    """
    Estimate IV percentile based on ticker characteristics.

    In production, this would use historical IV data.
    For demo, we use heuristics.
    """
    # High volatility stocks
    high_vol = ['TSLA', 'NVDA', 'AMD', 'GME', 'AMC', 'PLTR', 'COIN']
    # Medium-high volatility
    med_high_vol = ['AAPL', 'AMZN', 'GOOGL', 'META', 'NFLX', 'MSFT']
    # Low volatility
    low_vol = ['KO', 'PG', 'JNJ', 'WMT', 'T', 'VZ']

    ticker_upper = ticker.upper()

    if ticker_upper in high_vol:
        return 70.0  # High IV
    elif ticker_upper in med_high_vol:
        return 55.0  # Medium-high IV
    elif ticker_upper in low_vol:
        return 35.0  # Low IV
    else:
        return 50.0  # Default medium


def estimate_iv(ticker: str) -> float:
    """
    Estimate current IV level.

    In production, this would come from options data.
    """
    high_vol = ['TSLA', 'NVDA', 'AMD', 'GME', 'AMC', 'PLTR', 'COIN']
    med_high_vol = ['AAPL', 'AMZN', 'GOOGL', 'META', 'NFLX', 'MSFT']
    low_vol = ['KO', 'PG', 'JNJ', 'WMT', 'T', 'VZ']

    ticker_upper = ticker.upper()

    if ticker_upper in high_vol:
        return 0.45  # 45% IV
    elif ticker_upper in med_high_vol:
        return 0.32  # 32% IV
    elif ticker_upper in low_vol:
        return 0.20  # 20% IV
    else:
        return 0.30  # Default


def generate_candidates_for_ticker(
    ticker: str,
    price: float = None,
    dte: int = 42,
    allowed_widths: list = None
) -> list:
    """
    Generate realistic option spread candidates for a ticker.

    Args:
        ticker: Stock symbol
        price: Current stock price (will fetch if None)
        dte: Days to expiration
        allowed_widths: List of allowed spread widths (uses config default if None)

    Returns:
        List of CreditSpreadCandidate objects
    """
    ticker = ticker.upper()

    # Get current price
    if price is None:
        price = get_stock_price(ticker)
        if price is None:
            print(f"  ⚠️  Could not fetch price for {ticker}, using estimate")
            # Use some defaults based on ticker
            price_estimates = {
                'AAPL': 180.0, 'MSFT': 415.0, 'GOOGL': 165.0,
                'AMZN': 185.0, 'TSLA': 250.0, 'NVDA': 135.0,
                'META': 520.0, 'SPY': 575.0, 'QQQ': 465.0
            }
            price = price_estimates.get(ticker, 100.0)

    print(f"  Generating candidates for {ticker} @ ${price:.2f}")

    # Get IV estimates
    iv = estimate_iv(ticker)
    iv_percentile = estimate_iv_percentile(ticker)

    candidates = []

    # Determine spread widths
    if allowed_widths is not None:
        # Use provided widths from config
        widths = allowed_widths
    else:
        # Fallback: determine spread width based on stock price
        if price > 500:
            widths = [10, 15]
        elif price > 200:
            widths = [5, 10]
        elif price > 100:
            widths = [5]
        else:
            widths = [2.5, 5]

    # Generate multiple strike combinations
    # Target deltas: 15, 18, 20, 25, 30 (different risk profiles)
    target_deltas = [0.15, 0.18, 0.20, 0.25, 0.30]

    for width in widths:
        for target_delta in target_deltas:
            # For bull put spreads:
            # Sell put at ~X% below current price based on delta
            # Delta 0.15 ≈ 10% OTM, 0.20 ≈ 8% OTM, 0.30 ≈ 5% OTM
            delta_to_otm = {
                0.15: 0.90,  # 10% OTM
                0.18: 0.92,  # 8% OTM
                0.20: 0.93,  # 7% OTM
                0.25: 0.95,  # 5% OTM
                0.30: 0.97,  # 3% OTM
            }

            otm_factor = delta_to_otm.get(target_delta, 0.93)

            # Round to nearest strike (typically $5 or $10 increments)
            strike_increment = 5 if price > 100 else 2.5
            short_strike = round((price * otm_factor) / strike_increment) * strike_increment
            long_strike = short_strike - width

            # Estimate volume and OI (higher for closer to ATM)
            base_volume = 200 + (target_delta * 1000)
            base_oi = 1000 + (target_delta * 3000)

            # Adjust for ticker liquidity
            liquid_tickers = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'TSLA', 'NVDA']
            if ticker in liquid_tickers:
                base_volume *= 2
                base_oi *= 2

            try:
                candidate = create_candidate_from_strikes(
                    underlying=ticker,
                    expiry="2026-02-20",
                    short_strike=short_strike,
                    long_strike=long_strike,
                    short_delta=-target_delta,  # Negative for puts
                    short_iv=iv,
                    volume=int(base_volume),
                    open_interest=int(base_oi),
                    dte=dte,
                    underlying_price=price
                )
                candidates.append(candidate)
            except Exception as e:
                print(f"  Warning: Could not create candidate at {short_strike}/{long_strike}: {e}")

    return candidates


def print_banner():
    """Print welcome banner."""
    print("\n" + "=" * 70)
    print(" DISCIPLINED CREDIT SPREAD SCREENER")
    print("=" * 70)
    print("\n📍 Philosophy:")
    print("   We're selling overpriced insurance repeatedly without dying.")
    print("   We're NOT predicting markets or timing tops/bottoms.")
    print("\n" + "=" * 70 + "\n")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Disciplined Credit Spread Screener - Find the best credit spread opportunities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Screen single ticker (conservative mode)
  %(prog)s --tickers AAPL

  # Screen multiple tickers (strict mode)
  %(prog)s --tickers AAPL,MSFT,TSLA --mode strict

  # Aggressive screening with custom VIX
  %(prog)s --tickers NVDA,AMD --mode aggressive --vix 18.5

  # Show top 10 recommendations
  %(prog)s --tickers SPY,QQQ --top 10

  # Quiet mode (only show best trade)
  %(prog)s --tickers AAPL --quiet

Screening Modes:
  conservative - Balanced approach (default)
  strict       - High standards, safer trades
  aggressive   - More opportunities, higher risk
        '''
    )

    parser.add_argument(
        '--tickers', '-t',
        type=str,
        required=True,
        help='Comma-separated list of ticker symbols (e.g., AAPL,MSFT,TSLA)'
    )

    parser.add_argument(
        '--mode', '-m',
        type=str,
        choices=['conservative', 'strict', 'aggressive'],
        default='conservative',
        help='Screening mode (default: conservative)'
    )

    parser.add_argument(
        '--vix',
        type=float,
        default=None,
        help='Manually specify VIX level (otherwise fetched automatically)'
    )

    parser.add_argument(
        '--dte',
        type=int,
        default=42,
        help='Days to expiration for spreads (default: 42)'
    )

    parser.add_argument(
        '--top', '-n',
        type=int,
        default=5,
        help='Number of top recommendations to show (default: 5)'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Quiet mode - only show best trade, no runner-ups'
    )

    parser.add_argument(
        '--no-filter-stats',
        action='store_true',
        help='Hide filter rejection statistics'
    )

    parser.add_argument(
        '--widths',
        type=str,
        default=None,
        help='Comma-separated spread widths (e.g., 5,7,10). Overrides config defaults.'
    )

    return parser.parse_args()


def get_config_for_mode(mode: str) -> ScreeningConfig:
    """
    Get screening config for selected mode.

    Args:
        mode: 'conservative', 'strict', or 'aggressive'

    Returns:
        ScreeningConfig object
    """
    if mode == 'strict':
        return ScreeningConfig(
            min_vix=16.0,
            min_iv_percentile=60.0,
            min_volume=200,
            min_open_interest=2000,
            target_delta_min=0.10,
            target_delta_max=0.15,
            max_abs_delta=0.15,
            max_recommendations=3
        )
    elif mode == 'aggressive':
        return ScreeningConfig(
            min_vix=12.0,
            min_iv_percentile=30.0,
            min_volume=50,
            min_open_interest=500,
            target_delta_min=0.20,
            target_delta_max=0.35,
            max_abs_delta=0.35,
            max_recommendations=10
        )
    else:  # conservative (default)
        return ScreeningConfig()


def main():
    """Main screening flow."""
    # Parse arguments
    args = parse_args()

    # Parse tickers
    tickers = [t.strip().upper() for t in args.tickers.split(',')]
    tickers = [t for t in tickers if t]  # Remove empty strings

    if not tickers:
        print("❌ Error: No valid tickers provided")
        return 1

    # Print banner
    print_banner()

    print(f"📊 Configuration:")
    print(f"   Tickers: {', '.join(tickers)}")
    print(f"   Mode: {args.mode.upper()}")
    print(f"   DTE: {args.dte} days")
    print("─" * 70)

    # Create config
    config = get_config_for_mode(args.mode)
    config.max_recommendations = args.top

    # Override spread widths if specified
    if args.widths:
        try:
            config.allowed_widths = [float(w.strip()) for w in args.widths.split(',')]
            print(f"   Using custom spread widths: {config.allowed_widths}")
        except ValueError:
            print(f"   ⚠️  Invalid widths format: {args.widths}, using defaults")

    screener = DisciplinedScreener(config)

    # Get VIX
    print("\n📊 Fetching market data...")
    if args.vix is not None:
        vix = args.vix
        print(f"   Using manual VIX: {vix:.2f}")
    else:
        vix = get_current_vix()
        print(f"   Current VIX: {vix:.2f}")

    # Check VIX
    if vix < config.min_vix:
        print(f"\n⚠️  WARNING: VIX ({vix:.2f}) is below minimum threshold ({config.min_vix})")
        print("   Premium is likely too cheap to trade.")
        print("   Most candidates may be rejected by market filter.")

    # Generate candidates for all tickers
    print("\n🔍 Generating option candidates...")
    all_candidates = []

    for ticker in tickers:
        print(f"\n  {ticker}:")
        ticker_candidates = generate_candidates_for_ticker(
            ticker,
            dte=args.dte,
            allowed_widths=config.allowed_widths
        )
        print(f"    Generated {len(ticker_candidates)} spread candidates")
        all_candidates.extend(ticker_candidates)

    print(f"\n✓ Total candidates across all tickers: {len(all_candidates)}")

    # Screen
    print("\n" + "=" * 70)
    print("⚡ APPLYING HARD FILTERS")
    print("=" * 70)

    recommendations = screener.screen(all_candidates, vix)

    # Print rejection stats (unless suppressed)
    if not args.no_filter_stats:
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
        print("\nThis is GOOD, not bad. Discipline means saying NO to most opportunities.")
        print("\nPossible reasons:")
        print("  • VIX too low (cheap premium)")
        print("  • IV percentile below threshold")
        print("  • Risk/reward ratios poor")
        print("  • Execution quality concerns")
        print("\n💡 Try again when:")
        print("  • VIX is elevated (>15)")
        print("  • Market shows signs of uncertainty")
        print("  • Different tickers with higher IV")
        return 0

    # Show top recommendation
    print("\n" + "=" * 70)
    print("🏆 TOP RECOMMENDATION")
    print("=" * 70)

    best = recommendations[0]
    print(best.format_output())

    # Show runner-ups if available and not in quiet mode
    if not args.quiet and len(recommendations) > 1:
        runner_ups = min(args.top - 1, len(recommendations) - 1)
        print("\n" + "=" * 70)
        print(f"📊 RUNNER-UPS (Top {runner_ups})")
        print("=" * 70)

        for i, rec in enumerate(recommendations[1:runner_ups+1], 2):
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

    if not args.quiet:
        print("\n" + "=" * 70)
        print("🔑 KEY TAKEAWAYS")
        print("=" * 70)
        print("  • High rejection rate is GOOD (discipline in action)")
        print("  • EV is your truth serum (never trade negative EV)")
        print("  • IV percentile > raw IV (sell when premium is rich)")
        print("  • Slippage matters more than most think")
        print("  • Better to wait than force mediocre trades")
        print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n✋ Screening cancelled by user.\n")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
