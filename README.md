# CryptEx

A minimal but functional crypto trading pipeline that connects to Binance, retrieves market data, generates trading signals, and places orders. Built for demonstration of exchange integration, data pipelines, and safe order execution.

## System Architecture

```
     ┌─────────────────────────────────────────────────────────────────┐
     │                    cryptex/cli.py (orchestrator)                │
     └─────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────────┐         ┌───────────────────┐
│ exchange/     │         │ data/             │         │ strategy/         │
│ client.py     │◄────────│ market_data.py    │────────►│ simple_signal.py  │
│ BinanceClient │         │ (caching, store)  │         │ MA-based signal   │
└───────┬───────┘         └───────────────────┘         └─────────┬─────────┘
        │                                                         │
        │                  ┌───────────────────┐                  │
        └─────────────────►│ execution/        │◄─────────────────┘
                           │ order_manager.py  │
                           │ (safety checks)   │
                           └───────────────────┘
```

### Components

| Module | Responsibility |
|--------|----------------|
| `exchange/client.py` | Binance REST API client: klines, ticker, account, orders |
| `data/market_data.py` | Fetches OHLCV data with TTL cache; persists to `.data/` |
| `strategy/simple_signal.py` | Price vs moving average → LONG / SHORT / HOLD |
| `execution/order_manager.py` | Places orders with duplicate/cooldown checks |
| `config.py` | Loads `.env` / `.env.default`; validates settings |

## Design Decisions

1. **Testnet by default** – Uses Binance Spot Testnet (`testnet.binance.vision`) to avoid real funds. Production URL can be set via `BINANCE_BASE_URL`.

2. **Simple MA signal** – Last close vs 20-period SMA. Not intended for profitability; demonstrates signal abstraction.

3. **Caching** – Market data cached for `DATA_CACHE_TTL_SECONDS` (default 30s) to reduce API calls and respect rate limits.

4. **Safety checks** – Order manager skips placement if open orders exist or cooldown (60s) is active.

5. **Dry run mode** – `DRY_RUN=true` logs intended orders without sending them. Useful when credentials are missing or for testing.

6. **Local persistence** – Candles saved to `.data/{SYMBOL}_{TIMEFRAME}.json` for debugging and offline analysis.

7. **Async I/O** – Uses `httpx` for non-blocking HTTP; klines and ticker fetched concurrently for better performance.

## How to Run

### 1. Install the package

**For use only** (run the CLI):

```bash
uv sync
```

**For development** (run tests, lint, debug):

```bash
uv sync --all-extras
```

### 2. Configure

```bash
touch .env.default
# Edit .env file: set BINANCE_API_KEY and BINANCE_API_SECRET
# Get testnet keys at https://testnet.binance.vision/
```

### 3. Run the pipeline

```bash
# After install
cryptex run --dry-run
cryptex run --live
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BINANCE_API_KEY` | — | Required. API key |
| `BINANCE_API_SECRET` | — | Required. API secret |
| `BINANCE_BASE_URL` | `https://testnet.binance.vision/api` | Exchange API base |
| `TRADING_SYMBOL` | `BTCUSDT` | Trading pair |
| `TIMEFRAME` | `5m` | Candle interval (1m, 5m, 15m, etc.) |
| `POSITION_SIZE` | `0.001` | Base asset quantity per order |
| `MA_PERIOD` | `20` | Moving average period for signal |
| `DATA_CACHE_TTL_SECONDS` | `30` | Cache validity in seconds |
| `DRY_RUN` | `true` | If true, simulate orders only |

## Limitations and Potential Improvements

### Limitations

- **Spot only** – No futures or margin. Binance Spot Testnet has limited pairs.
- **Single run** – One signal/order per execution. No continuous loop or scheduler.
- **Fixed position size** – No risk-based sizing or portfolio logic.
- **Basic error handling** – Retries and backoff are minimal.
- **No position tracking** – Does not reconcile with exchange positions.

### Potential Improvements

- Add a scheduler (e.g. `schedule` or cron) for periodic runs.
- Implement retry with exponential backoff for API failures.
- Add WebSocket streams for real-time data instead of polling.
- Support limit orders with configurable offset from mark price.
- Add structured logging (JSON) and metrics for production.
- Integrate a lightweight DB (SQLite) for order/position history.

## Project Structure

```
CryptEx/
├── cryptex/
│   ├── __init__.py
│   ├── __main__.py         # python -m cryptex
│   ├── cli.py              # CLI entry point (cryptex command)
│   ├── config.py           # Configuration
│   ├── exchange/
│   │   └── client.py       # Binance API client
│   ├── data/
│   │   └── market_data.py  # Market data + cache
│   ├── strategy/
│   │   └── simple_signal.py # Signal generation
│   └── execution/
│       └── order_manager.py # Order execution
├── pyproject.toml          # Package config (setuptools)
├── requirements.txt
└── README.md
```


## Running Tests

```bash
uv sync --all-extras

pytest tests/ -v
# With coverage: pytest tests/ -v --cov=cryptex
```
