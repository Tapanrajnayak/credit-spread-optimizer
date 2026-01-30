#!/usr/bin/env python3
"""
Real market data fetching for credit spread optimizer.

Integrates with python-options-core to fetch:
- Current stock prices
- Options chains
- Calculate Greeks
- Evaluate spread quality
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta

from .models import CreditSpread, SpreadType

# Try to import yfinance
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
    print("Warning: yfinance not installed. Install with: pip install yfinance")

# Import from python-options-core (now in separate namespace, no collision)
CoreOptionData = None
CoreOptionType = None
HAS_OPTIONS_CORE = False

try:
    from models import OptionData as CoreOptionData, OptionType as CoreOptionType
    from greeks.calculator import calculate_greeks
    from spreads.evaluator import SpreadEvaluator
    HAS_OPTIONS_CORE = True
except ImportError:
    pass  # Silently disable if not available


class OptionsChainFetcher:
    """Fetch and process options chains from yfinance."""

    def __init__(self):
        if not HAS_YFINANCE:
            raise ImportError("yfinance is required for live market data. Install with: pip install yfinance")
        self.spread_evaluator = SpreadEvaluator() if HAS_OPTIONS_CORE else None

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current stock price."""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except Exception as e:
            print(f"  ⚠ Error fetching price for {ticker}: {e}")
        return None

    def get_options_expirations(self, ticker: str) -> List[str]:
        """Get available options expiration dates."""
        try:
            stock = yf.Ticker(ticker)
            return list(stock.options)
        except Exception as e:
            print(f"  ⚠ Error fetching expirations for {ticker}: {e}")
            return []

    def get_options_chain(self, ticker: str, expiration: str) -> Optional[Dict]:
        """Get options chain for specific expiration."""
        try:
            stock = yf.Ticker(ticker)
            chain = stock.option_chain(expiration)
            return {
                'calls': chain.calls,
                'puts': chain.puts,
                'expiration': expiration
            }
        except Exception as e:
            print(f"  ⚠ Error fetching chain for {ticker} {expiration}: {e}")
            return None

    def find_expiration_by_dte(
        self,
        ticker: str,
        min_dte: int,
        max_dte: int
    ) -> Optional[str]:
        """Find expiration date within DTE range."""
        expirations = self.get_options_expirations(ticker)
        if not expirations:
            return None

        today = datetime.now()

        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
            dte = (exp_date - today).days

            if min_dte <= dte <= max_dte:
                return exp_str

        # If no exact match, return closest
        if expirations:
            exp_dates = [datetime.strptime(e, "%Y-%m-%d") for e in expirations]
            dtes = [(exp - today).days for exp in exp_dates]

            # Find closest to midpoint of range
            target_dte = (min_dte + max_dte) // 2
            closest_idx = min(range(len(dtes)), key=lambda i: abs(dtes[i] - target_dte))

            return expirations[closest_idx]

        return None

    def create_option_data(self, row, option_type: str) -> Optional['CoreOptionData']:
        """Convert yfinance option row to CoreOptionData."""
        if not HAS_OPTIONS_CORE:
            return None

        try:
            opt_type = CoreOptionType.CALL if option_type == 'call' else CoreOptionType.PUT

            return CoreOptionData(
                strike=float(row['strike']),
                option_type=opt_type,
                bid=float(row['bid']) if row['bid'] > 0 else float(row['lastPrice']) * 0.95,
                ask=float(row['ask']) if row['ask'] > 0 else float(row['lastPrice']) * 1.05,
                mid=float(row['lastPrice']),
                last=float(row['lastPrice']),
                volume=int(row['volume']) if row['volume'] > 0 else 0,
                open_interest=int(row['openInterest']) if row['openInterest'] > 0 else 0,
                implied_volatility=float(row['impliedVolatility']) if row['impliedVolatility'] > 0 else 0.25
            )
        except Exception as e:
            print(f"  ⚠ Error creating OptionData: {e}")
            return None

    def find_strike_by_delta(
        self,
        options_df,
        target_delta: float,
        option_type: str,
        spot: float,
        dte: int
    ) -> Optional[float]:
        """
        Find strike closest to target delta.

        For puts: target_delta should be negative (e.g., -0.30)
        For calls: target_delta should be positive (e.g., 0.30)
        """
        if options_df.empty:
            return None

        # Sort by strike
        options_df = options_df.sort_values('strike')

        best_strike = None
        best_delta_diff = float('inf')

        for _, row in options_df.iterrows():
            strike = row['strike']

            # Estimate delta using simple approximation
            # For ATM options, delta ≈ 0.50
            # Further OTM = lower delta
            if option_type == 'put':
                # Put delta is negative
                moneyness = strike / spot
                estimated_delta = -(0.5 * moneyness) if moneyness < 1 else -0.05
            else:
                # Call delta is positive
                moneyness = strike / spot
                estimated_delta = (0.5 / moneyness) if moneyness > 1 else 0.95

            delta_diff = abs(estimated_delta - target_delta)

            if delta_diff < best_delta_diff:
                best_delta_diff = delta_diff
                best_strike = strike

        return best_strike

    def build_credit_spread(
        self,
        ticker: str,
        spot: float,
        spread_type: SpreadType,
        short_strike: float,
        long_strike: float,
        options_chain: Dict,
        dte: int,
        debug: bool = False
    ) -> Optional[CreditSpread]:
        """Build CreditSpread from real market data."""

        try:
            option_type = 'put' if spread_type == SpreadType.BULL_PUT else 'call'
            df = options_chain['puts'] if option_type == 'put' else options_chain['calls']

            # Find short and long legs in chain
            short_row = df[df['strike'] == short_strike]
            long_row = df[df['strike'] == long_strike]

            if short_row.empty:
                if debug:
                    print(f"    DEBUG: Short strike ${short_strike:.0f} not found in chain")
                return None

            if long_row.empty:
                if debug:
                    print(f"    DEBUG: Long strike ${long_strike:.0f} not found in chain")
                return None

            short_row = short_row.iloc[0]
            long_row = long_row.iloc[0]
        except Exception as e:
            if debug:
                print(f"    DEBUG: Error finding strikes: {e}")
            return None

        # Create OptionData objects
        if HAS_OPTIONS_CORE:
            short_option = self.create_option_data(short_row, option_type)
            long_option = self.create_option_data(long_row, option_type)

            if not short_option or not long_option:
                return None

            # Evaluate spread quality
            short_quality = self.spread_evaluator.evaluate_option(short_option, contracts=1)
            long_quality = self.spread_evaluator.evaluate_option(long_option, contracts=1)

            # Take worst quality
            quality_ratings = ["excellent", "good", "acceptable", "poor", "avoid"]
            short_idx = quality_ratings.index(short_quality.rating)
            long_idx = quality_ratings.index(long_quality.rating)
            worst_rating = quality_ratings[max(short_idx, long_idx)]

            spread_quality_rating = worst_rating
            slippage = short_quality.total_slippage + long_quality.total_slippage
            liquidity_score = (short_option.liquidity_score + long_option.liquidity_score) / 2

        else:
            # Fallback if python-options-core not available
            spread_quality_rating = "good"
            slippage = 10.0
            liquidity_score = float(short_row['volume']) + float(short_row['openInterest']) * 0.5

        # Calculate P&L
        try:
            short_bid = float(short_row['bid']) if short_row['bid'] > 0 else float(short_row['lastPrice']) * 0.98
            short_ask = float(short_row['ask']) if short_row['ask'] > 0 else float(short_row['lastPrice']) * 1.02
            long_bid = float(long_row['bid']) if long_row['bid'] > 0 else float(long_row['lastPrice']) * 0.98
            long_ask = float(long_row['ask']) if long_row['ask'] > 0 else float(long_row['lastPrice']) * 1.02

            if spread_type == SpreadType.BULL_PUT:
                credit = short_bid - long_ask
            else:  # BEAR_CALL
                credit = short_bid - long_ask

            if debug:
                print(f"    DEBUG: Short ${short_strike:.0f} bid=${short_bid:.2f} ask=${short_ask:.2f}")
                print(f"    DEBUG: Long ${long_strike:.0f} bid=${long_bid:.2f} ask=${long_ask:.2f}")
                print(f"    DEBUG: Credit = ${credit:.2f}")

            width = abs(short_strike - long_strike)
            max_profit = (credit * 100) - slippage
            max_loss = (width * 100) - (credit * 100)
        except Exception as e:
            if debug:
                print(f"    DEBUG: Error calculating P&L: {e}")
            return None

        # Estimate Greeks (simplified)
        # In production, use greeks.calculator from python-options-core
        if option_type == 'put':
            short_delta = -float(short_row['impliedVolatility']) * 0.5 if short_strike < spot else -0.05
            long_delta = -float(long_row['impliedVolatility']) * 0.3 if long_strike < spot else -0.02
        else:
            short_delta = float(short_row['impliedVolatility']) * 0.5 if short_strike > spot else 0.95
            long_delta = float(long_row['impliedVolatility']) * 0.3 if long_strike > spot else 0.98

        net_delta = short_delta + long_delta

        # Theta estimation
        theta = width * 0.015  # Rough approximation

        # Probability and EV
        probability_profit = 1.0 - abs(short_delta)
        prob_loss = 1.0 - probability_profit
        expected_value = (probability_profit * max_profit) - (prob_loss * max_loss)
        roc = (expected_value / max_loss) * 100 * (30 / dte) if max_loss > 0 and dte > 0 else 0.0

        # Breakeven
        if spread_type == SpreadType.BULL_PUT:
            breakeven = short_strike - credit
        else:
            breakeven = short_strike + credit

        # Build CreditSpread
        try:
            spread = CreditSpread(
                ticker=ticker,
                spread_type=spread_type,
                short_strike=short_strike,
                long_strike=long_strike,
                credit=credit,
                width=width,
                dte=dte,
                delta=net_delta,
                theta=theta,
                gamma=0.02,
                vega=-width * 0.1,
                spread_quality_rating=spread_quality_rating,
                iv_percentile=65.0,  # TODO: Calculate from historical data
                liquidity_score=liquidity_score,
                slippage=slippage,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven=breakeven,
                probability_profit=probability_profit,
                expected_value=expected_value,
                return_on_capital=roc,
                short_delta=short_delta,
                long_delta=long_delta,
                short_iv=float(short_row['impliedVolatility']) if short_row['impliedVolatility'] > 0 else 0.25,
                long_iv=float(long_row['impliedVolatility']) if long_row['impliedVolatility'] > 0 else 0.25,
                skew=(float(short_row['impliedVolatility']) if short_row['impliedVolatility'] > 0 else 0.25) -
                     (float(long_row['impliedVolatility']) if long_row['impliedVolatility'] > 0 else 0.25)
            )
            return spread
        except Exception as e:
            if debug:
                print(f"    DEBUG: Error building CreditSpread: {e}")
            return None

    def generate_spreads_from_market(
        self,
        ticker: str,
        spread_type: SpreadType,
        widths: List[int],
        min_dte: int,
        max_dte: int,
        target_short_delta: float = -0.30,
        debug: bool = False
    ) -> List[CreditSpread]:
        """Generate credit spreads from real market data."""

        spreads = []

        # Get current price
        spot = self.get_current_price(ticker)
        if not spot:
            print(f"  ✗ Could not fetch price for {ticker}")
            return spreads

        if debug:
            print(f"  Spot price: ${spot:.2f}")

        # Find suitable expiration
        expiration = self.find_expiration_by_dte(ticker, min_dte, max_dte)
        if not expiration:
            print(f"  ✗ No expiration found for {ticker} in {min_dte}-{max_dte} DTE range")
            return spreads

        # Calculate DTE
        exp_date = datetime.strptime(expiration, "%Y-%m-%d")
        dte = (exp_date - datetime.now()).days

        if debug:
            print(f"  Using expiration: {expiration} ({dte} DTE)")

        # Get options chain
        chain = self.get_options_chain(ticker, expiration)
        if not chain:
            print(f"  ✗ Could not fetch options chain for {ticker}")
            return spreads

        option_type = 'put' if spread_type == SpreadType.BULL_PUT else 'call'
        options_df = chain['puts'] if option_type == 'put' else chain['calls']

        if options_df.empty:
            print(f"  ✗ No {option_type} options found")
            return spreads

        if debug:
            print(f"  Total {option_type} options: {len(options_df)}")

        # Find strikes around target delta
        # For bull put spread, we want strikes below spot
        # For bear call spread, we want strikes above spot
        if spread_type == SpreadType.BULL_PUT:
            viable_strikes = options_df[options_df['strike'] < spot]['strike'].values
        else:
            viable_strikes = options_df[options_df['strike'] > spot]['strike'].values

        if debug:
            print(f"  Viable OTM strikes: {len(viable_strikes)}")
            if len(viable_strikes) > 0:
                print(f"  Strike range: ${min(viable_strikes):.0f} - ${max(viable_strikes):.0f}")

        if len(viable_strikes) == 0:
            print(f"  ✗ No viable OTM strikes found")
            return spreads

        # Generate spreads at different strikes
        tried = 0
        built = 0
        for short_strike in sorted(viable_strikes, reverse=(spread_type == SpreadType.BULL_PUT))[:10]:  # Try top 10
            for width in widths:
                if spread_type == SpreadType.BULL_PUT:
                    long_strike = short_strike - width
                else:
                    long_strike = short_strike + width

                # Check if long strike exists
                if long_strike not in options_df['strike'].values:
                    if debug:
                        print(f"  Skip ${short_strike:.0f}/${long_strike:.0f}: long strike not found")
                    continue

                tried += 1
                spread = self.build_credit_spread(
                    ticker=ticker,
                    spot=spot,
                    spread_type=spread_type,
                    short_strike=short_strike,
                    long_strike=long_strike,
                    options_chain=chain,
                    dte=dte,
                    debug=debug
                )

                if spread:
                    if spread.credit > 0:
                        spreads.append(spread)
                        built += 1
                        if debug:
                            print(f"  ✓ Built ${short_strike:.0f}/${long_strike:.0f}: credit=${spread.credit:.2f}")
                    else:
                        if debug:
                            print(f"  ✗ Skip ${short_strike:.0f}/${long_strike:.0f}: negative credit (${spread.credit:.2f})")
                else:
                    if debug:
                        print(f"  ✗ Skip ${short_strike:.0f}/${long_strike:.0f}: build failed")

        print(f"  Generated {len(spreads)} spreads from market data (tried {tried}, built {built})")
        return spreads
