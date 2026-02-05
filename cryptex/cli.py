"""Command-line interface for the CryptEx trading pipeline."""

import asyncclick as click
from loguru import logger

from .config import Config
from .data.market_data import MarketDataService
from .exchange.client import BinanceClient
from .execution.order_manager import OrderManager
from .strategy.simple_signal import Signal, SimpleSignalStrategy


async def run_pipeline(config: Config, dry_run: bool = False) -> int:
    """Run one iteration of the trading pipeline. Returns 0 on success, 1 on error."""
    api_key = config.binance_api_key or "dry-run"
    api_secret = config.binance_api_secret or "dry-run"
    client = BinanceClient(
        api_key=api_key,
        api_secret=api_secret,
        base_url=config.binance_base_url,
    )

    try:
        if not await client.ping():
            logger.error("Failed to connect to Binance. Check API URL and network.")
            return 1

        logger.info("Connected to Binance ({})", config.binance_base_url)

        market_data = MarketDataService(
            client=client,
            symbol=config.symbol,
            timeframe=config.timeframe,
            cache_ttl_seconds=config.data_cache_ttl_seconds,
        )

        candles, price = await market_data.get_klines_and_ticker(limit=100)
        if not candles:
            logger.error("No market data retrieved")
            return 1

        logger.info(
            "Market data: {} {} - {} candles, last close={:.2f}, ticker={:.2f}",
            config.symbol,
            config.timeframe,
            len(candles),
            candles[-1].close,
            price,
        )

        strategy = SimpleSignalStrategy(ma_period=config.ma_period)
        signal = strategy.generate(candles)
        ma = strategy.compute_ma(candles)
        logger.info(
            "Signal: {} (close={:.2f}, MA({})={:.2f})",
            signal.value,
            candles[-1].close,
            config.ma_period,
            ma or 0,
        )

        if signal == Signal.HOLD:
            logger.info("HOLD signal - no order to place")
            return 0

        if dry_run:
            logger.info(
                "[DRY RUN] Would place {} order: {} {}",
                config.order_type,
                "BUY" if signal == Signal.LONG else "SELL",
                config.position_size,
            )
            return 0

        order_manager = OrderManager(
            client=client,
            symbol=config.symbol,
            position_size=config.position_size,
            order_type=config.order_type,
        )

        result = await order_manager.execute(signal)
        if result.success:
            logger.info("Order placed successfully: {}", result.order_id)
        else:
            logger.warning("Order not placed: {}", result.message)

        return 0
    finally:
        await client.close()


@click.group()
def cli() -> None:
    """CryptEx - Minimal crypto trading pipeline for Binance."""


@cli.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate orders without placing them",
)
@click.option(
    "--live",
    is_flag=True,
    help="Place real orders (overrides DRY_RUN env)",
)
async def run(dry_run: bool, live: bool) -> None:
    """Run one iteration of the trading pipeline."""
    config = Config()
    if live:
        config.dry_run = False
    elif dry_run:
        config.dry_run = True

    errors = config.validate()
    if errors:
        for err in errors:
            logger.error("Config error: {}", err)
        logger.info(
            "Copy .env.example to .env and set BINANCE_API_KEY, BINANCE_API_SECRET. "
            "Get testnet keys at https://testnet.binance.vision/"
        )
        raise SystemExit(1)

    exit_code = await run_pipeline(config, dry_run=config.dry_run)
    raise SystemExit(exit_code)
