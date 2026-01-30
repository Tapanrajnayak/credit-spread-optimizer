#!/usr/bin/env python3
"""
Credit Spread Optimizer - Command Line Interface

Screen and rank credit spreads across multiple tickers using multi-factor analysis.

Usage:
    python main.py AAPL MSFT TSLA
    python main.py --tickers AAPL,MSFT,GOOGL --min-iv 60 --min-roc 10
    python main.py SPY QQQ --spread-type bull_put --width 5 --dte 30-45
    python main.py AAPL --verbose --top 10
"""

import sys
import argparse
from typing import List
from cso.models import (
    SpreadType, ScreeningCriteria, OptimizationWeights
)
from cso.spread_screener import CreditSpreadScreener, create_mock_spread
from cso.spread_optimizer import SpreadOptimizer
from cso.market_data import OptionsChainFetcher


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Screen and rank credit spreads across multiple tickers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic scan of tech stocks
  python main.py AAPL MSFT GOOGL AMZN

  # Scan with custom filters
  python main.py SPY QQQ --min-iv 60 --min-roc 10 --max-delta 0.20

  # Bull put spreads with specific width
  python main.py TSLA --spread-type bull_put --width 10 --dte 35-40

  # Verbose output showing all details
  python main.py AAPL MSFT --verbose --top 10

  # Custom optimization weights (emphasize IV and theta)
  python main.py SPY --weight-iv 0.35 --weight-theta 0.30

Screening Criteria Defaults:
  IV Percentile:     >= 50 (sell when IV is elevated)
  Liquidity:         >= 1000 (volume + OI score)
  Spread Quality:    <= 6% bid-ask spread
  Delta:             <= 0.30 (near-neutral)
  Theta:             >= 0.05 (minimum daily income)
  Probability:       >= 65% win rate
  Expected Value:    >= 0 (positive edge)
  ROC:               >= 8% monthly
  DTE:               30-45 days (theta sweet spot)

Output:
  - Summary by ticker
  - Top N spreads overall
  - Detailed analysis of best spread
  - Filter statistics
  - Greeks and risk metrics
        """
    )

    # Positional arguments
    parser.add_argument(
        "tickers",
        nargs="*",
        help="Stock/ETF symbols to scan (e.g., AAPL MSFT TSLA)"
    )

    # Ticker input options
    parser.add_argument(
        "--tickers",
        dest="tickers_flag",
        type=str,
        help="Comma-separated list of tickers (alternative to positional)"
    )

    # Spread configuration
    parser.add_argument(
        "--spread-type",
        choices=["bull_put", "bear_call", "both"],
        default="bull_put",
        help="Type of credit spread to analyze (default: bull_put)"
    )

    parser.add_argument(
        "--width",
        type=int,
        nargs="+",
        default=[5, 10],
        help="Strike widths to analyze (default: 5 10)"
    )

    parser.add_argument(
        "--dte",
        type=str,
        default="30-45",
        help="Days to expiration range (default: 30-45)"
    )

    # Screening filters
    parser.add_argument(
        "--min-iv",
        type=float,
        default=50.0,
        help="Minimum IV percentile (default: 50)"
    )

    parser.add_argument(
        "--min-liquidity",
        type=float,
        default=1000.0,
        help="Minimum liquidity score (default: 1000)"
    )

    parser.add_argument(
        "--max-spread",
        type=float,
        default=6.0,
        help="Maximum bid-ask spread %% (default: 6.0)"
    )

    parser.add_argument(
        "--max-delta",
        type=float,
        default=0.30,
        help="Maximum absolute delta (default: 0.30)"
    )

    parser.add_argument(
        "--min-theta",
        type=float,
        default=0.05,
        help="Minimum daily theta (default: 0.05)"
    )

    parser.add_argument(
        "--min-prob",
        type=float,
        default=0.65,
        help="Minimum probability of profit (default: 0.65)"
    )

    parser.add_argument(
        "--min-ev",
        type=float,
        default=0.0,
        help="Minimum expected value (default: 0.0)"
    )

    parser.add_argument(
        "--min-roc",
        type=float,
        default=8.0,
        help="Minimum monthly ROC %% (default: 8.0)"
    )

    # Optimization weights
    parser.add_argument(
        "--weight-iv",
        type=float,
        default=0.25,
        help="Weight for IV percentile (default: 0.25)"
    )

    parser.add_argument(
        "--weight-theta",
        type=float,
        default=0.20,
        help="Weight for theta efficiency (default: 0.20)"
    )

    parser.add_argument(
        "--weight-quality",
        type=float,
        default=0.15,
        help="Weight for spread quality (default: 0.15)"
    )

    parser.add_argument(
        "--weight-prob",
        type=float,
        default=0.15,
        help="Weight for probability (default: 0.15)"
    )

    parser.add_argument(
        "--weight-ev",
        type=float,
        default=0.15,
        help="Weight for expected value (default: 0.15)"
    )

    parser.add_argument(
        "--weight-liquidity",
        type=float,
        default=0.10,
        help="Weight for liquidity (default: 0.10)"
    )

    # Data source
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data for testing (default: use live market data)"
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live market data from yfinance (default, kept for clarity)"
    )

    # Output options
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of top spreads to show (default: 5)"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed technical analysis"
    )

    parser.add_argument(
        "--per-ticker",
        type=int,
        default=2,
        help="Top spreads to show per ticker (default: 2)"
    )

    parser.add_argument(
        "--sort-by",
        choices=["score", "ev", "roc", "theta", "prob"],
        default="score",
        help="Sort results by metric (default: score)"
    )

    args = parser.parse_args()

    # Merge ticker sources
    if args.tickers_flag:
        args.tickers.extend(args.tickers_flag.split(","))

    # Clean up ticker list
    args.tickers = [t.strip().upper() for t in args.tickers if t.strip()]

    if not args.tickers:
        parser.error("At least one ticker must be provided")

    return args


def parse_dte_range(dte_str: str) -> tuple:
    """Parse DTE range string like '30-45' into (min, max)."""
    if "-" in dte_str:
        min_dte, max_dte = dte_str.split("-")
        return (int(min_dte.strip()), int(max_dte.strip()))
    else:
        dte = int(dte_str.strip())
        return (dte, dte)


def generate_mock_candidates(ticker: str, spot: float, widths: List[int], dte: int, spread_type: SpreadType):
    """Generate mock spread candidates for testing."""
    candidates = []

    # Generate spreads at different strikes
    for i in range(6):
        pct_below = 0.05 * (i + 1)  # 5%, 10%, 15%, 20%, 25%, 30% below spot

        for width in widths:
            if spread_type == SpreadType.BULL_PUT:
                short_strike = spot * (1 - pct_below)
                long_strike = short_strike - width
            else:  # BEAR_CALL
                short_strike = spot * (1 + pct_below)
                long_strike = short_strike + width

            spread = create_mock_spread(
                ticker=ticker,
                spread_type=spread_type,
                short_strike=round(short_strike),
                long_strike=round(long_strike),
                short_delta=-0.20 - (i * 0.03),  # Vary delta
                short_iv=0.28 + (i * 0.01),      # Vary IV
                dte=dte
            )

            # Vary characteristics
            spread.iv_percentile = 65 - (i * 2)
            spread.liquidity_score = 2000 - (i * 100)

            candidates.append(spread)

    return candidates


def print_header(title: str):
    """Print formatted section header."""
    print()
    print("=" * 80)
    print(title.center(80))
    print("=" * 80)


def print_subheader(title: str):
    """Print formatted subsection header."""
    print()
    print(title)
    print("-" * 80)


def print_ticker_summary(results: dict, args):
    """Print summary results by ticker."""
    if not args.verbose:
        # Compact summary
        print(f"\n{'Ticker':<8} {'Screened':<10} {'Passed':<10} {'Pass%':<8} {'Top Spread'}")
        print("-" * 80)
        for ticker, result in sorted(results.items()):
            pass_pct = f"{result.pass_rate:.0f}%"
            if result.top_spreads:
                s = result.top_spreads[0]
                top = f"${s.short_strike:.0f}/${s.long_strike:.0f} Score:{s.composite_score:.0f} EV:${s.expected_value:.0f}"
            else:
                top = "None"
            print(f"{ticker:<8} {result.total_candidates:<10} {result.passed_filters:<10} {pass_pct:<8} {top}")
    else:
        # Verbose summary
        print_header("RESULTS BY TICKER")
        for ticker, result in sorted(results.items()):
            print(f"\n{ticker}: {result.passed_filters}/{result.total_candidates} passed ({result.pass_rate:.0f}%)")
            if result.top_spreads:
                for i, spread in enumerate(result.top_spreads[:args.per_ticker], 1):
                    print(f"  {i}. ${spread.short_strike:.0f}/${spread.long_strike:.0f} "
                          f"Score:{spread.composite_score:.0f} "
                          f"EV:${spread.expected_value:.0f} "
                          f"ROC:{spread.return_on_capital:.0f}% "
                          f"P:{spread.probability_profit:.0%}")


def print_top_spreads(all_spreads: List, args, optimizer: SpreadOptimizer):
    """Print top N spreads overall."""
    # Sort by requested metric
    metric_map = {
        "score": "composite_score",
        "ev": "expected_value",
        "roc": "return_on_capital",
        "theta": "theta",
        "prob": "probability_profit"
    }

    if args.sort_by == "score":
        top = optimizer.rank_spreads(all_spreads, limit=args.top)
    else:
        top = optimizer.get_top_n_by_metric(all_spreads, metric_map[args.sort_by], n=args.top)

    print(f"\nTOP {args.top} SPREADS (by {args.sort_by.upper()}):")
    print(f"{'#':<3} {'Ticker':<7} {'Strikes':<13} {'W':<3} {'Score':<6} {'EV':<8} {'ROC%':<7} {'P%':<5} {'Theta':<8}")
    print("-" * 80)

    for i, spread in enumerate(top, 1):
        strikes = f"{spread.short_strike:.0f}/{spread.long_strike:.0f}"
        print(f"{i:<3} {spread.ticker:<7} ${strikes:<12} {spread.width:>2.0f} "
              f"{spread.composite_score:>5.0f} "
              f"${spread.expected_value:>6.0f} "
              f"{spread.return_on_capital:>6.0f} "
              f"{spread.probability_profit:>4.0%} "
              f"${spread.theta:>6.2f}")


def print_best_spread_details(spread, verbose: bool = False):
    """Print detailed analysis of best spread."""
    if verbose:
        # Detailed view
        print_header("BEST SPREAD - DETAILED ANALYSIS")
        print(f"\n{spread.ticker} ${spread.short_strike:.0f}/${spread.long_strike:.0f} {spread.spread_type.value.replace('_', ' ').title()}")
        print(f"Width: {spread.width:.0f}pt | DTE: {spread.dte}d | Score: {spread.composite_score:.0f}/100")

        # Score breakdown
        quality_map = {"excellent": 100, "good": 75, "acceptable": 50, "poor": 25, "avoid": 0}
        iv_score = spread.iv_percentile
        theta_score = min(100, (spread.theta_efficiency / 2.0) * 100)
        quality_score = quality_map.get(spread.spread_quality_rating, 50)
        prob_score = spread.probability_profit * 100
        ev_score = max(0, min(100, 50 + (spread.expected_value / 2.0)))
        liq_score = min(100, (spread.liquidity_score / 5000) * 100)

        print(f"\nScore Breakdown (weighted):")
        print(f"  IV={iv_score:.0f}(25%) Theta={theta_score:.0f}(20%) Quality={quality_score}(15%) "
              f"Prob={prob_score:.0f}(15%) EV={ev_score:.0f}(15%) Liq={liq_score:.0f}(10%)")

        print(f"\nP&L: Credit=${spread.credit:.2f} MaxProfit=${spread.max_profit:.0f} MaxLoss=${spread.max_loss:.0f} Breakeven=${spread.breakeven:.2f}")
        print(f"Greeks: Delta={spread.delta:+.2f} Theta=${spread.theta:.2f}/d (Eff={spread.theta_efficiency:.3f}%) Gamma={spread.gamma:.2f} Vega={spread.vega:+.2f}")
        print(f"Risk: P(win)={spread.probability_profit:.0%} EV=${spread.expected_value:.0f} ROC={spread.return_on_capital:.0f}%/mo")
        print(f"Quality: {spread.spread_quality_rating.upper()} | IV%ile={spread.iv_percentile:.0f} | Liquidity={spread.liquidity_score:.0f}")

        if spread.composite_score >= 70:
            rating = "STRONG BUY"
        elif spread.composite_score >= 60:
            rating = "BUY"
        elif spread.composite_score >= 50:
            rating = "CONSIDER"
        else:
            rating = "MARGINAL"
        print(f"→ {rating}")
    else:
        # Compact view
        print(f"\nBEST: {spread.ticker} ${spread.short_strike:.0f}/${spread.long_strike:.0f} "
              f"Score:{spread.composite_score:.0f} EV:${spread.expected_value:.0f} "
              f"ROC:{spread.return_on_capital:.0f}% P:{spread.probability_profit:.0%} "
              f"Credit:${spread.credit:.2f} MaxLoss:${spread.max_loss:.0f}")


def print_filter_summary(args):
    """Print active filter settings."""
    print_header("SCREENING CRITERIA")

    print(f"\nFilters Applied:")
    print(f"  IV Percentile:      >= {args.min_iv:.0f}")
    print(f"  Liquidity Score:    >= {args.min_liquidity:.0f}")
    print(f"  Bid-Ask Spread:     <= {args.max_spread:.1f}%")
    print(f"  Delta (absolute):   <= {args.max_delta:.2f}")
    print(f"  Daily Theta:        >= ${args.min_theta:.2f}")
    print(f"  Probability:        >= {args.min_prob:.0%}")
    print(f"  Expected Value:     >= ${args.min_ev:.2f}")
    print(f"  Monthly ROC:        >= {args.min_roc:.1f}%")
    print(f"  DTE Range:          {args.dte}")

    print(f"\nOptimization Weights:")
    print(f"  IV Percentile:      {args.weight_iv:.0%}")
    print(f"  Theta Efficiency:   {args.weight_theta:.0%}")
    print(f"  Spread Quality:     {args.weight_quality:.0%}")
    print(f"  Probability:        {args.weight_prob:.0%}")
    print(f"  Expected Value:     {args.weight_ev:.0%}")
    print(f"  Liquidity:          {args.weight_liquidity:.0%}")


def main():
    """Main entry point."""
    args = parse_args()

    # Determine data source (default to live unless --mock specified)
    use_live_data = not args.mock

    # Print configuration
    print("=" * 80)
    print(f"CREDIT SPREAD OPTIMIZER | {', '.join(args.tickers)} | "
          f"{args.spread_type.replace('_', ' ').title()} | "
          f"Width:{','.join(str(w) for w in args.width)} | "
          f"DTE:{args.dte} | "
          f"{'LIVE' if use_live_data else 'MOCK'} data")
    print("=" * 80)

    if args.verbose:
        print_filter_summary(args)

    # Parse DTE range
    min_dte, max_dte = parse_dte_range(args.dte)

    # Create screening criteria
    criteria = ScreeningCriteria(
        min_iv_percentile=args.min_iv,
        min_liquidity_score=args.min_liquidity,
        max_spread_pct=args.max_spread,
        max_delta=args.max_delta,
        min_theta=args.min_theta,
        min_probability_profit=args.min_prob,
        min_expected_value=args.min_ev,
        min_roc=args.min_roc,
        dte_range=(min_dte, max_dte)
    )

    # Create optimization weights
    weights = OptimizationWeights(
        iv_percentile=args.weight_iv,
        theta_efficiency=args.weight_theta,
        spread_quality=args.weight_quality,
        probability_profit=args.weight_prob,
        expected_value=args.weight_ev,
        liquidity=args.weight_liquidity
    )

    # Validate weights
    if not weights.validate():
        print("\n⚠ Warning: Optimization weights don't sum to 1.0, normalizing...")
        total = (weights.iv_percentile + weights.theta_efficiency +
                weights.spread_quality + weights.probability_profit +
                weights.expected_value + weights.liquidity)
        weights.iv_percentile /= total
        weights.theta_efficiency /= total
        weights.spread_quality /= total
        weights.probability_profit /= total
        weights.expected_value /= total
        weights.liquidity /= total

    # Create screener
    screener = CreditSpreadScreener(criteria=criteria, weights=weights)
    optimizer = SpreadOptimizer(weights=weights)

    spread_type_enum = SpreadType.BULL_PUT if args.spread_type == "bull_put" else SpreadType.BEAR_CALL

    # Generate candidates
    ticker_candidates = {}

    if use_live_data:
        # Use real market data
        if args.verbose:
            print(f"\nFetching live market data...")
        fetcher = OptionsChainFetcher()

        for ticker in args.tickers:
            if args.verbose:
                print(f"\n{ticker}:")
            candidates = fetcher.generate_spreads_from_market(
                ticker=ticker,
                spread_type=spread_type_enum,
                widths=args.width,
                min_dte=min_dte,
                max_dte=max_dte,
                target_short_delta=-0.30 if spread_type_enum == SpreadType.BULL_PUT else 0.30,
                debug=args.verbose  # Enable debug output if verbose mode
            )
            ticker_candidates[ticker] = candidates
            if not args.verbose:
                print(f"{ticker}: {len(candidates)} spreads", end=" ")

    else:
        # Use mock data
        if args.verbose:
            print(f"\nGenerating mock candidates...")

        # Mock spot prices
        spot_prices = {
            "AAPL": 175.0, "MSFT": 380.0, "GOOGL": 140.0, "AMZN": 175.0,
            "TSLA": 250.0, "SPY": 450.0, "QQQ": 380.0, "IWM": 200.0,
            "META": 350.0, "NVDA": 500.0, "AMD": 140.0, "NFLX": 450.0
        }
        default_spot = 100.0

        for ticker in args.tickers:
            spot = spot_prices.get(ticker, default_spot)
            candidates = generate_mock_candidates(
                ticker=ticker,
                spot=spot,
                widths=args.width,
                dte=(min_dte + max_dte) // 2,  # Use midpoint
                spread_type=spread_type_enum
            )
            ticker_candidates[ticker] = candidates
            print(f"{ticker}: {len(candidates)} spreads", end=" ")

    print()  # Newline

    # Screen all tickers
    total = sum(len(c) for c in ticker_candidates.values())
    if args.verbose:
        print(f"\nScreening {total} total spreads...")
    results = screener.screen_multiple_tickers(ticker_candidates, top_n_per_ticker=args.per_ticker)

    # Print results by ticker
    print_ticker_summary(results, args)

    # Get all passing spreads
    all_spreads = []
    for result in results.values():
        all_spreads.extend(result.top_spreads)

    if not all_spreads:
        print("\n⚠ NO SPREADS PASSED FILTERS")
        print("Try: Lower --min-iv/--min-prob/--min-roc or increase --max-delta/--max-spread or use --verbose")
        return 1

    # Print top spreads
    print_top_spreads(all_spreads, args, optimizer)

    # Print best spread details
    best = optimizer.find_best_spread(all_spreads)
    print_best_spread_details(best, verbose=args.verbose)

    # Summary statistics
    if args.verbose:
        total = sum(r.total_candidates for r in results.values())
        print(f"\nSUMMARY: {len(args.tickers)} tickers | {total} candidates | "
              f"{len(all_spreads)} passed ({len(all_spreads)/total*100:.0f}%) | "
              f"Best: {best.ticker} Score:{best.composite_score:.0f} "
              f"EV:${max(s.expected_value for s in all_spreads):.0f} "
              f"ROC:{max(s.return_on_capital for s in all_spreads):.0f}%")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
