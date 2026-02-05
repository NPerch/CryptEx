"""Tests for BinanceClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cryptex.exchange.client import BinanceClient, BinanceClientError


@pytest.fixture
def client() -> BinanceClient:
    """BinanceClient instance for tests."""
    return BinanceClient(
        api_key="test-key",
        api_secret="test-secret",
        base_url="https://testnet.binance.vision/api",
    )


class TestBinanceClientSign:
    """Tests for _sign method."""

    def test_sign_produces_hex_string(self, client: BinanceClient) -> None:
        """Signature should be a hex string."""
        params = {"symbol": "BTCUSDT", "timestamp": 1234567890}
        sig = client._sign(params)
        assert isinstance(sig, str)
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

    def test_sign_deterministic(self, client: BinanceClient) -> None:
        """Same params should produce same signature."""
        params = {"symbol": "BTCUSDT", "timestamp": 1234567890}
        assert client._sign(params) == client._sign(params)

    def test_sign_different_params_different_output(self, client: BinanceClient) -> None:
        """Different params should produce different signatures."""
        sig1 = client._sign({"a": "1"})
        sig2 = client._sign({"a": "2"})
        assert sig1 != sig2


class TestBinanceClientPing:
    """Tests for ping method."""

    @pytest.mark.asyncio
    async def test_ping_success(self, client: BinanceClient) -> None:
        """Ping returns True when API responds."""
        with patch.object(client, "_request", new_callable=AsyncMock, return_value={}):
            result = await client.ping()
            assert result is True

    @pytest.mark.asyncio
    async def test_ping_raises_on_error(self, client: BinanceClient) -> None:
        """Ping raises BinanceClientError when API fails."""
        with patch.object(
            client,
            "_request",
            new_callable=AsyncMock,
            side_effect=BinanceClientError("Connection failed"),
        ):
            with pytest.raises(BinanceClientError, match="Connection failed"):
                await client.ping()


class TestBinanceClientGetKlines:
    """Tests for get_klines method."""

    @pytest.mark.asyncio
    async def test_get_klines_success(self, client: BinanceClient) -> None:
        """get_klines returns data from API."""
        mock_data = [[1000000, "50000", "50100", "49900", "50050", "100"]] * 5
        with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_data):
            result = await client.get_klines("BTCUSDT", "5m", limit=5)
            assert len(result) == 5
            client._request.assert_called_once()
            call_args = client._request.call_args
            assert call_args[0][1] == "/v3/klines"
            params = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("params", {})
            assert params["symbol"] == "BTCUSDT"
            assert params["interval"] == "5m"
            assert params["limit"] == 5

    @pytest.mark.asyncio
    async def test_get_klines_with_start_end_time(self, client: BinanceClient) -> None:
        """get_klines passes start_time and end_time when provided."""
        with patch.object(client, "_request", new_callable=AsyncMock, return_value=[]):
            await client.get_klines(
                "BTCUSDT", "5m",
                start_time=1000000,
                end_time=2000000,
            )
            params = client._request.call_args[0][2]
            assert params["startTime"] == 1000000
            assert params["endTime"] == 2000000


class TestBinanceClientGetTickerPrice:
    """Tests for get_ticker_price method."""

    @pytest.mark.asyncio
    async def test_get_ticker_price_success(self, client: BinanceClient) -> None:
        """get_ticker_price returns price dict."""
        with patch.object(
            client, "_request",
            new_callable=AsyncMock,
            return_value={"symbol": "BTCUSDT", "price": "50000.00"},
        ):
            result = await client.get_ticker_price("BTCUSDT")
            assert result["price"] == "50000.00"
            assert result["symbol"] == "BTCUSDT"


class TestBinanceClientPlaceMarketOrder:
    """Tests for place_market_order method."""

    @pytest.mark.asyncio
    async def test_place_market_order_quantity(self, client: BinanceClient) -> None:
        """place_market_order uses quantity when quote_order_qty not provided."""
        with patch.object(
            client, "_request",
            new_callable=AsyncMock,
            return_value={"orderId": "123", "status": "FILLED"},
        ):
            await client.place_market_order("BTCUSDT", "BUY", quantity=0.001)
            params = client._request.call_args[0][2]
            assert params["quantity"] == 0.001
            assert "quoteOrderQty" not in params

    @pytest.mark.asyncio
    async def test_place_market_order_quote_qty(self, client: BinanceClient) -> None:
        """place_market_order uses quoteOrderQty when provided."""
        with patch.object(
            client, "_request",
            new_callable=AsyncMock,
            return_value={"orderId": "123", "status": "FILLED"},
        ):
            await client.place_market_order(
                "BTCUSDT", "BUY",
                quantity=0,
                quote_order_qty=500.0,
            )
            params = client._request.call_args[0][2]
            assert params["quoteOrderQty"] == 500.0
            assert "quantity" not in params


class TestBinanceClientErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_request_timeout_raises(self, client: BinanceClient) -> None:
        """Timeout raises BinanceClientError."""
        with patch.object(client, "_get_client", new_callable=AsyncMock) as mock_get:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_get.return_value = mock_http

            with pytest.raises(BinanceClientError, match="timed out"):
                await client._request("GET", "/v3/ping")

    @pytest.mark.asyncio
    async def test_request_http_error_raises(self, client: BinanceClient) -> None:
        """HTTP error raises BinanceClientError with message."""
        with patch.object(client, "_get_client", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "400", request=MagicMock(), response=mock_response
            )
            mock_response.json.return_value = {"msg": "Invalid symbol"}
            mock_response.text = "Bad Request"

            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_http

            with pytest.raises(BinanceClientError, match="Invalid symbol"):
                await client._request("GET", "/v3/klines", {"symbol": "INVALID"})
