"""Tests for OrderManager."""

from unittest.mock import AsyncMock

import pytest

from cryptex.exchange.client import BinanceClientError
from cryptex.execution.order_manager import OrderManager, OrderResult
from cryptex.strategy.simple_signal import Signal


@pytest.fixture
def order_manager(mock_binance_client: AsyncMock) -> OrderManager:
    """OrderManager with mocked client."""
    return OrderManager(
        client=mock_binance_client,
        symbol="BTCUSDT",
        position_size=0.001,
        order_cooldown_seconds=1,
    )


class TestOrderResult:
    """Tests for OrderResult dataclass."""

    def test_success_result(self) -> None:
        """OrderResult with success=True."""
        result = OrderResult(success=True, order_id="123", message="OK")
        assert result.success is True
        assert result.order_id == "123"

    def test_failure_result(self) -> None:
        """OrderResult with success=False."""
        result = OrderResult(success=False, message="Rejected")
        assert result.success is False
        assert result.message == "Rejected"


class TestOrderManagerExecute:
    """Tests for OrderManager.execute."""

    @pytest.mark.asyncio
    async def test_hold_returns_success_no_order(
        self, order_manager: OrderManager
    ) -> None:
        """HOLD signal returns success without placing order."""
        result = await order_manager.execute(Signal.HOLD)
        assert result.success is True
        assert "HOLD" in result.message
        order_manager.client.place_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_long_places_buy_order(
        self, order_manager: OrderManager, mock_binance_client: AsyncMock
    ) -> None:
        """LONG signal places BUY order."""
        mock_binance_client.get_open_orders = AsyncMock(return_value=[])
        result = await order_manager.execute(Signal.LONG)
        assert result.success is True
        assert result.order_id == "12345"
        mock_binance_client.place_market_order.assert_called_once_with(
            symbol="BTCUSDT", side="BUY", quantity=0.001
        )

    @pytest.mark.asyncio
    async def test_short_places_sell_order(
        self, order_manager: OrderManager, mock_binance_client: AsyncMock
    ) -> None:
        """SHORT signal places SELL order."""
        mock_binance_client.get_open_orders = AsyncMock(return_value=[])
        result = await order_manager.execute(Signal.SHORT)
        assert result.success is True
        mock_binance_client.place_market_order.assert_called_once_with(
            symbol="BTCUSDT", side="SELL", quantity=0.001
        )

    @pytest.mark.asyncio
    async def test_skips_when_open_orders_exist(
        self, order_manager: OrderManager, mock_binance_client: AsyncMock
    ) -> None:
        """Skips order when open orders exist."""
        mock_binance_client.get_open_orders = AsyncMock(
            return_value=[{"orderId": "existing"}]
        )
        result = await order_manager.execute(Signal.LONG)
        assert result.success is False
        assert "open orders" in result.message.lower()
        mock_binance_client.place_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_on_api_error_fetching_orders(
        self, order_manager: OrderManager, mock_binance_client: AsyncMock
    ) -> None:
        """Assumes open orders exist when API fails to fetch."""
        mock_binance_client.get_open_orders = AsyncMock(
            side_effect=BinanceClientError("API error")
        )
        result = await order_manager.execute(Signal.LONG)
        assert result.success is False
        mock_binance_client.place_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_on_cooldown(
        self, order_manager: OrderManager, mock_binance_client: AsyncMock
    ) -> None:
        """Skips order when on cooldown for same side."""
        mock_binance_client.get_open_orders = AsyncMock(return_value=[])
        await order_manager.execute(Signal.LONG)
        mock_binance_client.place_market_order.reset_mock()
        result = await order_manager.execute(Signal.LONG)
        assert result.success is False
        assert "cooldown" in result.message.lower()
        mock_binance_client.place_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_order_rejection_returns_failure(
        self, order_manager: OrderManager, mock_binance_client: AsyncMock
    ) -> None:
        """Returns failure when exchange rejects order."""
        mock_binance_client.get_open_orders = AsyncMock(return_value=[])
        mock_binance_client.place_market_order = AsyncMock(
            side_effect=BinanceClientError("Insufficient balance")
        )
        result = await order_manager.execute(Signal.LONG)
        assert result.success is False
        assert "Insufficient balance" in result.message
