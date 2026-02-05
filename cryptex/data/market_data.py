"""Market data retrieval with caching and local storage."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptex.exchange.client import BinanceClient


@dataclass(slots=True)
class Candle:
    """OHLCV candlestick data."""

    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_binance(cls, raw: list) -> Candle:
        """Parse Binance kline format:
        [open_time, open, high, low, close, volume, ...].
        """
        return cls(
            open_time=int(raw[0]),
            open=float(raw[1]),
            high=float(raw[2]),
            low=float(raw[3]),
            close=float(raw[4]),
            volume=float(raw[5]),
        )


@dataclass(slots=True)
class MarketDataCache:
    """In-memory cache with TTL to avoid repeated API calls."""

    candles: list[Candle] = field(default_factory=list)
    ticker_price: float | None = None
    last_updated: float = 0
    ttl_seconds: int = 30

    def is_stale(self) -> bool:
        return time.time() - self.last_updated > self.ttl_seconds

    def update_candles(self, candles: list[Candle]) -> None:
        self.candles = candles
        self.last_updated = time.time()

    def update_ticker(self, price: float) -> None:
        self.ticker_price = price
        self.last_updated = time.time()


class MarketDataService:
    """Retrieves and caches market data from Binance (async)."""

    def __init__(
        self,
        client: BinanceClient,
        symbol: str,
        timeframe: str,
        cache_ttl_seconds: int = 30,
        data_dir: Path | None = None,
    ):
        self.client = client
        self.symbol = symbol
        self.timeframe = timeframe
        self._cache = MarketDataCache(ttl_seconds=cache_ttl_seconds)
        self._data_dir = data_dir or Path(".data")
        self._data_dir.mkdir(parents=True, exist_ok=True)

    async def get_klines(
        self, limit: int = 100, force_refresh: bool = False
    ) -> list[Candle]:
        """Get OHLCV candlestick data with caching.
        Avoids API calls if cache is valid.
        """
        if not force_refresh and not self._cache.is_stale() and self._cache.candles:
            logger.debug(
                "Returning cached klines ({} candles)", len(self._cache.candles)
            )
            return self._cache.candles

        logger.info(
            "Fetching klines for {} {} (limit={})", self.symbol, self.timeframe, limit
        )
        raw = await self.client.get_klines(
            symbol=self.symbol,
            interval=self.timeframe,
            limit=limit,
        )
        candles = [Candle.from_binance(k) for k in raw]
        self._cache.update_candles(candles)
        await self._persist_candles(candles)
        return candles

    async def get_ticker_price(self, force_refresh: bool = False) -> float:
        """Get current price with caching."""
        if (
            not force_refresh
            and not self._cache.is_stale()
            and self._cache.ticker_price
        ):
            return self._cache.ticker_price

        data = await self.client.get_ticker_price(self.symbol)
        price = float(data["price"])
        self._cache.update_ticker(price)
        return price

    async def get_klines_and_ticker(
        self, limit: int = 100, force_refresh: bool = False
    ) -> tuple[list[Candle], float]:
        """Fetch klines and ticker price concurrently for better performance."""
        klines_task = asyncio.create_task(self.get_klines(limit, force_refresh))
        ticker_task = asyncio.create_task(self.get_ticker_price(force_refresh))
        candles, price = await asyncio.gather(klines_task, ticker_task)
        return candles, price

    async def _persist_candles(self, candles: list[Candle]) -> None:
        """Store candles to local file (runs in thread pool to avoid blocking)."""
        filepath = self._data_dir / f"{self.symbol}_{self.timeframe}.json"
        data = [
            {
                "open_time": c.open_time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]

        def _write() -> None:
            try:
                with open(filepath, "w") as f:
                    json.dump(data, f, indent=2)
                logger.debug("Persisted {} candles to {}", len(candles), filepath)
            except OSError as e:
                logger.warning("Failed to persist candles: {}", e)

        await asyncio.to_thread(_write)
