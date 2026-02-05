"""Simple trading signal generation."""

from __future__ import annotations

from enum import StrEnum

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptex.data.market_data import Candle


class Signal(StrEnum):
    """Discrete trading decision."""

    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"


class SimpleSignalStrategy:
    """Extremely simple signal: price above/below moving average.

    - LONG: current close > MA
    - SHORT: current close < MA
    - HOLD: insufficient data or close == MA
    """

    def __init__(self, ma_period: int = 20):
        if ma_period < 2:
            msg = "ma_period must be at least 2"
            raise ValueError(msg)
        self.ma_period = ma_period

    def compute_ma(self, candles: list[Candle]) -> float | None:
        """Compute simple moving average of closes for the last ma_period candles."""
        if len(candles) < self.ma_period:
            return None
        closes = [c.close for c in candles[-self.ma_period :]]
        return sum(closes) / len(closes)

    def generate(self, candles: list[Candle]) -> Signal:
        """Generate trading signal from OHLCV data.

        Uses last candle close vs moving average.
        """
        if not candles:
            return Signal.HOLD

        ma = self.compute_ma(candles)
        if ma is None:
            return Signal.HOLD

        last_close = candles[-1].close

        if last_close > ma:
            return Signal.LONG
        if last_close < ma:
            return Signal.SHORT
        return Signal.HOLD
