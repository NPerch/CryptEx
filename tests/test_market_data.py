"""Tests for market data components."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cryptex.data.market_data import Candle, MarketDataCache, MarketDataService


class TestCandle:
    """Tests for Candle dataclass."""

    def test_from_binance_parses_correctly(self) -> None:
        """Candle.from_binance parses Binance kline format."""
        raw = [1000000, "50000", "50100", "49900", "50050", "100"]
        candle = Candle.from_binance(raw)
        assert candle.open_time == 1000000
        assert candle.open == 50000.0
        assert candle.high == 50100.0
        assert candle.low == 49900.0
        assert candle.close == 50050.0
        assert candle.volume == 100.0

    @pytest.mark.parametrize(
        "raw",
        [
            [1000000, "50000", "50100", "49900", "50050", "100", "extra"],
            [1000000, "50000", "50100", "49900", "50050", "100"],
        ],
    )
    def test_from_binance_handles_extra_fields(self, raw: list) -> None:
        """Candle.from_binance works with extra fields in raw data."""
        candle = Candle.from_binance(raw)
        assert candle.close == 50050.0


class TestMarketDataCache:
    """Tests for MarketDataCache."""

    def test_is_stale_empty_cache(self) -> None:
        """Empty cache is stale."""
        cache = MarketDataCache(ttl_seconds=30)
        assert cache.is_stale() is True

    def test_is_stale_fresh_update(self) -> None:
        """Cache is not stale immediately after update."""
        cache = MarketDataCache(ttl_seconds=30)
        cache.update_candles([Candle(0, 1, 2, 0, 1, 1)])
        assert cache.is_stale() is False

    def test_update_ticker(self) -> None:
        """update_ticker sets price and updates timestamp."""
        cache = MarketDataCache(ttl_seconds=30)
        cache.update_ticker(50000.0)
        assert cache.ticker_price == 50000.0
        assert cache.is_stale() is False


class TestMarketDataService:
    """Tests for MarketDataService."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Mock BinanceClient."""
        client = AsyncMock()
        client.get_klines = AsyncMock(return_value=[
            [1000000, "50000", "50100", "49900", "50050", "100"],
            [1000060, "50050", "50200", "50000", "50150", "110"],
        ])
        client.get_ticker_price = AsyncMock(return_value={"price": "50100.00"})
        return client

    @pytest.fixture
    def temp_data_dir(self, tmp_path: Path) -> Path:
        """Temporary directory for data persistence."""
        return tmp_path / "data"

    @pytest.mark.asyncio
    async def test_get_klines_fetches_and_caches(
        self, mock_client: AsyncMock, temp_data_dir: Path
    ) -> None:
        """get_klines fetches from API and caches result."""
        service = MarketDataService(
            client=mock_client,
            symbol="BTCUSDT",
            timeframe="5m",
            cache_ttl_seconds=30,
            data_dir=temp_data_dir,
        )
        candles = await service.get_klines(limit=10)
        assert len(candles) == 2
        assert candles[0].close == 50050.0
        mock_client.get_klines.assert_called_once_with(
            symbol="BTCUSDT", interval="5m", limit=10
        )

    @pytest.mark.asyncio
    async def test_get_klines_returns_cached_when_fresh(
        self, mock_client: AsyncMock, temp_data_dir: Path
    ) -> None:
        """get_klines returns cache when not stale."""
        service = MarketDataService(
            client=mock_client,
            symbol="BTCUSDT",
            timeframe="5m",
            cache_ttl_seconds=30,
            data_dir=temp_data_dir,
        )
        await service.get_klines(limit=10)
        mock_client.get_klines.reset_mock()
        candles = await service.get_klines(limit=10)
        assert len(candles) == 2
        mock_client.get_klines.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_klines_force_refresh(
        self, mock_client: AsyncMock, temp_data_dir: Path
    ) -> None:
        """get_klines with force_refresh bypasses cache."""
        service = MarketDataService(
            client=mock_client,
            symbol="BTCUSDT",
            timeframe="5m",
            cache_ttl_seconds=30,
            data_dir=temp_data_dir,
        )
        await service.get_klines(limit=10)
        mock_client.get_klines.reset_mock()
        await service.get_klines(limit=10, force_refresh=True)
        mock_client.get_klines.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_ticker_price(self, mock_client: AsyncMock, temp_data_dir: Path) -> None:
        """get_ticker_price returns float price."""
        service = MarketDataService(
            client=mock_client,
            symbol="BTCUSDT",
            timeframe="5m",
            data_dir=temp_data_dir,
        )
        price = await service.get_ticker_price()
        assert price == 50100.0
        mock_client.get_ticker_price.assert_called_once_with("BTCUSDT")

    @pytest.mark.asyncio
    async def test_get_klines_and_ticker_concurrent(
        self, mock_client: AsyncMock, temp_data_dir: Path
    ) -> None:
        """get_klines_and_ticker fetches both concurrently."""
        service = MarketDataService(
            client=mock_client,
            symbol="BTCUSDT",
            timeframe="5m",
            data_dir=temp_data_dir,
        )
        candles, price = await service.get_klines_and_ticker(limit=5)
        assert len(candles) == 2
        assert price == 50100.0
        mock_client.get_klines.assert_called_once()
        mock_client.get_ticker_price.assert_called_once()
