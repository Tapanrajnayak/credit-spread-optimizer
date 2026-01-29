# credit-spread-optimizer

Credit spread screening and ranking system for options traders. Screens candidates through hard filters (liquidity, IV percentile, delta, theta, expected value) and ranks survivors by composite score.

Two screening approaches:

- **Disciplined Screener** -- Fail-fast filtering with 9 hard rules. No curve fitting. Rejects ~80% of candidates by design.
- **Flexible Screener** -- Multi-factor weighted optimization across IV, theta, spread quality, and expected value.

## Install

```bash
pip install -e .
```

Requires [python-options-core](https://github.com/Tapanrajnayak/python-options-core):

```bash
cd ../python-options-core && pip install -e .
```

## Usage

### CLI (Disciplined Screener)

```bash
python3 examples/disciplined_screening_demo.py --tickers AAPL,MSFT,TSLA
python3 examples/disciplined_screening_demo.py --tickers NVDA --mode strict
python3 examples/disciplined_screening_demo.py --tickers SPY --quiet
```

### Python API (Flexible Screener)

```python
from spread_screener import CreditSpreadScreener
from spread_optimizer import SpreadOptimizer

screener = CreditSpreadScreener()
candidates = screener.screen_bull_put_spreads(ticker="AAPL", min_iv_percentile=50)

optimizer = SpreadOptimizer()
ranked = optimizer.rank_spreads(candidates)
best = ranked[0]
```

## Project Structure

```
credit-spread-optimizer/
├── main.py                  # CLI entry point
├── models.py                # Data models (CreditSpread, ScreeningCriteria)
├── filters.py               # 10 independent filter functions
├── analyzers.py             # IV, theta, probability, EV analyzers
├── spread_optimizer.py      # Composite scoring and ranking
├── spread_screener.py       # High-level screening API
├── market_data.py           # Live data integration (yfinance)
├── disciplined_models.py    # Disciplined system models
├── disciplined_screener.py  # Fail-fast screening engine
├── examples/                # Usage examples and demos
├── tests/                   # Unit tests
└── setup.py
```

## Dependencies

- numpy, pandas
- yfinance (optional, for live data)
- python-options-core (sibling package)

## License

MIT
