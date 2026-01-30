# credit-spread-optimizer

Credit spread screening and ranking system for options traders. Screens candidates through hard filters (liquidity, IV percentile, delta, theta, expected value) and ranks survivors by composite score.

Two screening approaches:

- **Disciplined Screener** -- Fail-fast filtering with 9 hard rules. No curve fitting. Rejects ~80% of candidates by design.
- **Flexible Screener** -- Multi-factor weighted optimization across IV, theta, spread quality, and expected value.

## Install

Create a virtual environment and install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For live market data (yfinance):

```bash
pip install -e ".[live]"
```

For development (pytest):

```bash
pip install -e ".[dev]"
```

Optional: install [python-options-core](https://github.com/Tapanrajnayak/python-options-core) for Greeks calculation and spread evaluation:

```bash
pip install -e ../python-options-core
```

The system degrades gracefully without it.

## Usage

### CLI (Flexible Screener)

```bash
python main.py AAPL MSFT TSLA
python main.py --tickers AAPL,MSFT,GOOGL --min-iv 60 --min-roc 10
python main.py SPY --spread-type bull_put --width 5 --dte 30-45
python main.py AAPL --verbose --top 10
```

### CLI (Disciplined Screener)

```bash
python examples/disciplined_screening_demo.py --tickers AAPL,MSFT,TSLA
python examples/disciplined_screening_demo.py --tickers NVDA --mode strict
python examples/disciplined_screening_demo.py --tickers SPY --quiet
python examples/disciplined_screening_demo.py --tickers NVDA,AMD --mode aggressive --vix 18.5
```

### Python API (Flexible Screener)

```python
from cso.models import SpreadType
from cso.spread_screener import CreditSpreadScreener, create_mock_spread

screener = CreditSpreadScreener()
candidates = [create_mock_spread("AAPL", SpreadType.BULL_PUT, short_strike=170.0, long_strike=165.0)]
result = screener.screen(candidates)

best = result.top_spreads[0] if result.top_spreads else None
```

### Quick Test (no live data needed)

```bash
python examples/quick_test.py
```

## Testing

```bash
pytest tests/
```

## Project Structure

```
credit-spread-optimizer/
├── main.py                  # CLI entry point (flexible screener)
├── cso/                     # Core package
│   ├── __init__.py          # Re-exports key classes
│   ├── models.py            # Data models (CreditSpread, ScreeningCriteria)
│   ├── filters.py           # 10 independent filter functions
│   ├── analyzers.py         # IV, theta, probability, EV analyzers
│   ├── spread_optimizer.py  # Composite scoring and ranking
│   ├── spread_screener.py   # High-level screening API
│   ├── market_data.py       # Live data integration (yfinance, optional)
│   ├── disciplined_models.py  # Disciplined system models
│   └── disciplined_screener.py  # Fail-fast screening engine
├── examples/
│   ├── disciplined_screening_demo.py  # Full CLI for disciplined screener
│   ├── quick_test.py                  # Quick smoke test (no live data)
│   ├── quick_interactive_test.py      # Interactive test
│   ├── basic_screening.py             # Flexible screener example
│   └── multi_ticker_scan.py           # Multi-ticker scan example
├── tests/
│   ├── test_filters.py      # Filter unit tests
│   └── test_optimizer.py    # Optimizer unit tests
└── setup.py
```

## Dependencies

- numpy, pandas (required)
- yfinance (optional -- live market data)
- python-options-core (optional -- Greeks calculation, spread evaluation)

## License

MIT
