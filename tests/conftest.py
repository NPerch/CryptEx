"""Pytest configuration and shared fixtures."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptex.config import Config
from cryptex.data.market_data import Candle
from cryptex.exchange.client import BinanceClient, BinanceClientError


@pytest.fixture
def config() -> Config:
    """Default config with testnet credentials for dry run."""
    return Config(
        binance_api_key="test-key",
        binance_api_secret="test-secret",
        binance_base_url="https://testnet.binance.vision/api",
        symbol="BTCUSDT",
        timeframe="5m",
        position_size=0.001,
        ma_period=20,
        dry_run=True,
    )


@pytest.fixture
def config_live() -> Config:
    """Config for live trading (requires credentials)."""
    return Config(
        binance_api_key="live-key",
        binance_api_secret="live-secret",
        symbol="BTCUSDT",
        dry_run=False,
    )


@pytest.fixture
def sample_klines() -> list[list]:
    """Sample Binance kline format data."""
    return [
        [1000000, "50000", "50100", "49900", "50050", "100", 1000100, "5000000", 100, "50", "50"],
        [1000060, "50050", "50200", "50000", "50150", "110", 1000160, "5520500", 110, "55", "55"],
        [1000120, "50150", "50300", "50100", "50200", "120", 1000220, "6024000", 120, "60", "60"],
        [1000180, "50200", "50400", "50150", "50350", "130", 1000280, "6545500", 130, "65", "65"],
        [1000240, "50350", "50500", "50300", "50400", "140", 1000340, "7056000", 140, "70", "70"],
    ]


@pytest.fixture
def sample_candles(sample_klines: list[list]) -> list[Candle]:
    """Sample Candle objects from klines."""
    return [Candle.from_binance(k) for k in sample_klines]


@pytest.fixture
def candles_above_ma() -> list[Candle]:
    """Candles where last close is above MA (LONG signal)."""
    # MA(3) of 10, 20, 30 = 20. Last close 50 > 20
    return [
        Candle(open_time=1, open=10, high=15, low=8, close=10, volume=100),
        Candle(open_time=2, open=15, high=25, low=12, close=20, volume=200),
        Candle(open_time=3, open=25, high=55, low=20, close=50, volume=300),
    ]


@pytest.fixture
def candles_below_ma() -> list[Candle]:
    """Candles where last close is below MA (SHORT signal)."""
    # MA(3) of 50, 40, 30 = 40. Last close 10 < 40
    return [
        Candle(open_time=1, open=55, high=60, low=45, close=50, volume=100),
        Candle(open_time=2, open=45, high=50, low=35, close=40, volume=200),
        Candle(open_time=3, open=35, high=15, low=5, close=10, volume=300),
    ]


@pytest.fixture
def candles_equal_ma() -> list[Candle]:
    """Candles where last close equals MA (HOLD signal)."""
    # MA(3) of 20, 20, 20 = 20. Last close 20 = 20
    return [
        Candle(open_time=1, open=18, high=22, low=15, close=20, volume=100),
        Candle(open_time=2, open=19, high=21, low=18, close=20, volume=200),
        Candle(open_time=3, open=20, high=21, low=19, close=20, volume=300),
    ]


@pytest.fixture
def mock_binance_client() -> AsyncMock:
    """Mock BinanceClient for unit tests."""
    client = AsyncMock(spec=BinanceClient)
    client.ping = AsyncMock(return_value=True)
    client.get_klines = AsyncMock(return_value=[])
    client.get_ticker_price = AsyncMock(return_value={"price": "50000.00"})
    client.get_open_orders = AsyncMock(return_value=[])
    client.place_market_order = AsyncMock(
        return_value={"orderId": "12345", "status": "FILLED"}
    )
    client.close = AsyncMock(return_value=None)
    return client


@pytest.fixture
def binance_client(mock_binance_client: AsyncMock) -> AsyncMock:
    """BinanceClient mock for integration-style tests."""
    return mock_binance_client
