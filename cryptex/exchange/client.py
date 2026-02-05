"""Binance REST API client for market data and order execution."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Self, TYPE_CHECKING
from urllib.parse import urlencode

import httpx
from loguru import logger

if TYPE_CHECKING:
    import sys
    from types import TracebackType


class BinanceClientError(Exception):
    """Raised when Binance API returns an error."""

    def __init__(self, message: str, response: httpx.Response | None = None):
        super().__init__(message)
        self.response = response


class BinanceClient:
    """Async client for Binance Spot REST API (supports testnet)."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://testnet.binance.vision/api",
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "X-MBX-APIKEY": self.api_key,
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        await self._get_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: sys.exc_info  # noqa: PYI036
        | tuple[type[BaseException], BaseException, TracebackType]
        | None,
    ) -> None:
        await self.close()

    def _sign(self, params: dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for signed endpoints."""
        query = urlencode(params)
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> dict[str, Any]:
        """Execute async HTTP request to Binance API."""
        params = params or {}
        url = f"{self.base_url}{endpoint}"

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)

        client = await self._get_client()
        try:
            if method.upper() == "GET":
                response = await client.get(url, params=params)
            else:
                response = await client.post(url, params=params)

            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException as e:
            logger.error("Binance API request timed out: {}", e)
            msg = f"Request timed out: {e}"
            raise BinanceClientError(msg) from e
        except httpx.HTTPStatusError as e:
            logger.error("Binance API request failed: {}", e)
            response = e.response
            try:
                err_body = response.json()
                msg = err_body.get("msg", str(e))
            except Exception:
                msg = response.text or str(e)
            raise BinanceClientError(msg, response) from e
        except httpx.RequestError as e:
            logger.error("Binance API request failed: {}", e)
            raise BinanceClientError(str(e)) from e

    # --- Public (unsigned) endpoints ---

    async def ping(self) -> bool:
        """Test connectivity to the exchange."""
        try:
            await self._request("GET", "/v3/ping")
            return True
        except BinanceClientError as e:
            logger.error("Ping failed: {}", e)
            raise BinanceClientError(str(e)) from e

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[list]:
        """Get OHLCV candlestick data.

        Returns list of [open_time, open, high, low, close, volume, ...]
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return await self._request("GET", "/v3/klines", params)

    async def get_ticker_price(self, symbol: str) -> dict[str, Any]:
        """Get latest price for a symbol."""
        params = {"symbol": symbol}
        return await self._request("GET", "/v3/ticker/price", params)

    # --- Private (signed) endpoints ---

    async def get_account(self) -> dict[str, Any]:
        """Get account information including balances."""
        return await self._request("GET", "/v3/account", signed=True)

    async def get_open_orders(self, symbol: str) -> list[dict]:
        """Get all open orders for a symbol."""
        params = {"symbol": symbol}
        return await self._request("GET", "/v3/openOrders", params, signed=True)

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        quote_order_qty: float | None = None,
    ) -> dict[str, Any]:
        """Place a market order.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            side: BUY or SELL
            quantity: Base asset quantity (use for BUY/SELL)
            quote_order_qty: Quote asset quantity (optional, for market BUY)
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
        }
        if quote_order_qty is not None:
            params["quoteOrderQty"] = quote_order_qty
        else:
            params["quantity"] = quantity

        logger.info("Placing market order: {} {} {}", side, symbol, params)
        result = await self._request("POST", "/v3/order", params, signed=True)
        logger.info("Order response: {}", result)
        return result
