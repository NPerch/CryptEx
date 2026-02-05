"""Tests for Config."""

import pytest
from pydantic import ValidationError

from cryptex.config import Config


class TestConfig:
    """Tests for Config."""

    def test_default_values(self) -> None:
        """Config has expected defaults."""
        config = Config()
        assert config.symbol == "BTCUSDT"
        assert config.timeframe == "5m"
        assert config.position_size == 0.001
        assert config.ma_period == 20
        assert config.binance_base_url == "https://testnet.binance.vision/api"

    def test_validate_dry_run_allows_empty_credentials(self) -> None:
        """When dry_run=True, empty credentials are valid."""
        config = Config(dry_run=True, binance_api_key="", binance_api_secret="")
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_requires_credentials_when_not_dry_run(self) -> None:
        """When dry_run=False, credentials are required."""
        config = Config(dry_run=False, binance_api_key="", binance_api_secret="")
        errors = config.validate()
        assert len(errors) >= 2
        assert any("BINANCE_API_KEY" in e for e in errors)
        assert any("BINANCE_API_SECRET" in e for e in errors)

    def test_validate_valid_credentials(self) -> None:
        """No errors when credentials provided and not dry run."""
        config = Config(
            dry_run=False,
            binance_api_key="key",
            binance_api_secret="secret",
        )
        errors = config.validate()
        assert len(errors) == 0

    @pytest.mark.parametrize("invalid_size", [0, -0.001, -1])
    def test_position_size_must_be_positive(self, invalid_size: float) -> None:
        """position_size must be > 0."""
        with pytest.raises(ValidationError):
            Config(position_size=invalid_size)

    @pytest.mark.parametrize("invalid_period", [0, 1])
    def test_ma_period_must_be_at_least_2(self, invalid_period: int) -> None:
        """ma_period must be >= 2."""
        with pytest.raises(ValidationError):
            Config(ma_period=invalid_period)
