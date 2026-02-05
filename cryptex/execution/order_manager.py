"""Order creation and execution with safety checks."""

from __future__ import annotations

import time
from dataclasses import dataclass

from loguru import logger
from cryptex.exchange.client import BinanceClient, BinanceClientError
from cryptex.strategy.simple_signal import Signal


@dataclass(slots=True, kw_only=True, frozen=True)
class OrderResult:
    """Result of an order attempt."""

    success: bool
    order_id: str | None = None
    message: str = ""
    response: dict | None = None


class OrderManager:
    """Manages order placement with safety checks:
    - Avoid duplicate orders (cooldown between same-direction orders)
    - Check for existing open orders before placing
    """

    def __init__(
        self,
        client: BinanceClient,
        symbol: str,
        position_size: float,
        order_type: str = "MARKET",
        order_cooldown_seconds: int = 60,
    ):
        self.client = client
        self.symbol = symbol
        self.position_size = position_size
        self.order_type = order_type.upper()
        self.order_cooldown_seconds = order_cooldown_seconds
        self._last_order_time: dict[str, float] = {}

    async def has_open_orders(self) -> bool:
        """Check if there are any open orders for the symbol."""
        try:
            orders = await self.client.get_open_orders(self.symbol)
            return len(orders) > 0
        except BinanceClientError as e:
            logger.error("Failed to fetch open orders: {}", e)
            return True  # Assume yes to be safe

    def _is_on_cooldown(self, side: str) -> bool:
        """Check if we're in cooldown period for this side."""
        last = self._last_order_time.get(side, 0)
        return (time.time() - last) < self.order_cooldown_seconds

    def _record_order(self, side: str) -> None:
        self._last_order_time[side] = time.time()

    async def execute(self, signal: Signal) -> OrderResult:
        """Execute order based on signal.

        - LONG -> BUY
        - SHORT -> SELL
        - HOLD -> no order
        """
        if signal == Signal.HOLD:
            return OrderResult(success=True, message="HOLD - no order placed")

        side = "BUY" if signal == Signal.LONG else "SELL"

        if await self.has_open_orders():
            msg = f"Skipping {side}: open orders exist for {self.symbol}"
            logger.warning(msg)
            return OrderResult(success=False, message=msg)

        if self._is_on_cooldown(side):
            msg = f"Skipping {side}: cooldown active ({self.order_cooldown_seconds}s)"
            logger.warning(msg)
            return OrderResult(success=False, message=msg)

        try:
            logger.info(
                "Placing %s order: %s %s",
                self.order_type,
                side,
                self.position_size,
            )
            result = await self.client.place_market_order(
                symbol=self.symbol,
                side=side,
                quantity=self.position_size,
            )
            self._record_order(side)
            order_id = str(result.get("orderId", ""))
            return OrderResult(
                success=True,
                order_id=order_id,
                message=f"Order placed: {order_id}",
                response=result,
            )
        except BinanceClientError as e:
            logger.error("Order rejected: {}", e)
            return OrderResult(
                success=False,
                message=str(e),
                response=getattr(e, "response", None),
            )
