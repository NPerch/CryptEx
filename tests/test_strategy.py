"""Tests for SimpleSignalStrategy and Signal."""

import pytest

from cryptex.data.market_data import Candle
from cryptex.strategy.simple_signal import Signal, SimpleSignalStrategy


class TestSimpleSignalStrategyInit:
    """Tests for SimpleSignalStrategy initialization."""

    def test_valid_ma_period(self) -> None:
        """Accepts ma_period >= 2."""
        strategy = SimpleSignalStrategy(ma_period=2)
        assert strategy.ma_period == 2

    def test_default_ma_period(self) -> None:
        """Default ma_period is 20."""
        strategy = SimpleSignalStrategy()
        assert strategy.ma_period == 20

    @pytest.mark.parametrize("invalid_period", [0, 1, -1])
    def test_invalid_ma_period_raises(self, invalid_period: int) -> None:
        """ma_period < 2 raises ValueError."""
        with pytest.raises(ValueError, match="ma_period must be at least 2"):
            SimpleSignalStrategy(ma_period=invalid_period)


class TestSimpleSignalStrategyComputeMa:
    """Tests for compute_ma method."""

    def test_insufficient_data_returns_none(self) -> None:
        """Returns None when fewer candles than ma_period."""
        strategy = SimpleSignalStrategy(ma_period=5)
        candles = [
            Candle(1, 10, 15, 8, 10, 100),
            Candle(2, 10, 15, 8, 20, 100),
        ]
        assert strategy.compute_ma(candles) is None

    def test_computes_correctly(self) -> None:
        """Computes simple moving average of closes."""
        strategy = SimpleSignalStrategy(ma_period=3)
        candles = [
            Candle(1, 10, 15, 8, 10, 100),
            Candle(2, 15, 25, 12, 20, 200),
            Candle(3, 25, 55, 20, 30, 300),
        ]
        ma = strategy.compute_ma(candles)
        assert ma == 20.0  # (10 + 20 + 30) / 3

    def test_uses_last_n_candles(self) -> None:
        """Uses only the last ma_period candles."""
        strategy = SimpleSignalStrategy(ma_period=2)
        candles = [
            Candle(1, 10, 15, 8, 100, 100),
            Candle(2, 15, 25, 12, 20, 200),
            Candle(3, 25, 55, 20, 30, 300),
        ]
        ma = strategy.compute_ma(candles)
        assert ma == 25.0  # (20 + 30) / 2, not including 100


class TestSimpleSignalStrategyGenerate:
    """Tests for generate method."""

    @pytest.mark.parametrize(
        "candles,expected",
        [
            ([], Signal.HOLD),
            ([Candle(1, 10, 15, 8, 10, 100)], Signal.HOLD),
        ],
    )
    def test_insufficient_data_returns_hold(
        self, candles: list[Candle], expected: Signal
    ) -> None:
        """Returns HOLD when insufficient data for MA."""
        strategy = SimpleSignalStrategy(ma_period=2)
        assert strategy.generate(candles) == expected

    def test_long_signal_when_close_above_ma(
        self, candles_above_ma: list[Candle]
    ) -> None:
        """Returns LONG when last close > MA."""
        strategy = SimpleSignalStrategy(ma_period=3)
        assert strategy.generate(candles_above_ma) == Signal.LONG

    def test_short_signal_when_close_below_ma(
        self, candles_below_ma: list[Candle]
    ) -> None:
        """Returns SHORT when last close < MA."""
        strategy = SimpleSignalStrategy(ma_period=3)
        assert strategy.generate(candles_below_ma) == Signal.SHORT

    def test_hold_signal_when_close_equals_ma(
        self, candles_equal_ma: list[Candle]
    ) -> None:
        """Returns HOLD when last close == MA."""
        strategy = SimpleSignalStrategy(ma_period=3)
        assert strategy.generate(candles_equal_ma) == Signal.HOLD

    @pytest.mark.parametrize(
        "closes,ma_period,expected",
        [
            ([10.0, 20.0, 30.0, 50.0], 3, Signal.LONG),  # 50 > (10+20+30)/3
            ([50.0, 40.0, 30.0, 10.0], 3, Signal.SHORT),  # 10 < (50+40+30)/3
            ([10.0, 30.0, 20.0], 3, Signal.HOLD),  # MA(3)=(10+30+20)/3=20, last=20
        ],
    )
    def test_signal_parametrized(
        self, closes: list[float], ma_period: int, expected: Signal
    ) -> None:
        """Parametrized signal generation tests."""
        candles = [
            Candle(open_time=i, open=c, high=c + 1, low=c - 1, close=c, volume=100)
            for i, c in enumerate(closes)
        ]
        strategy = SimpleSignalStrategy(ma_period=ma_period)
        assert strategy.generate(candles) == expected


class TestSignal:
    """Tests for Signal enum."""

    def test_signal_values(self) -> None:
        """Signal has expected string values."""
        assert Signal.LONG == "LONG"
        assert Signal.SHORT == "SHORT"
        assert Signal.HOLD == "HOLD"
