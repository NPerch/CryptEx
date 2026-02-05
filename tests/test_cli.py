"""Tests for CLI."""

from unittest.mock import AsyncMock, patch

import pytest
from asyncclick.testing import CliRunner

from cryptex.cli import cli, run_pipeline
from cryptex.config import Config


@pytest.fixture
def cli_runner() -> CliRunner:
    """AsyncClick CLI runner."""
    return CliRunner()


class TestCliGroup:
    """Tests for CLI group."""

    @pytest.mark.asyncio
    async def test_cli_help(self, cli_runner: CliRunner) -> None:
        """cli shows help with subcommands."""
        result = await cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.output

    @pytest.mark.asyncio
    async def test_run_help(self, cli_runner: CliRunner) -> None:
        """run command shows help."""
        result = await cli_runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "dry-run" in result.output
        assert "live" in result.output


class TestRunCommand:
    """Tests for run command."""

    @pytest.mark.asyncio
    async def test_run_validates_config(self, cli_runner: CliRunner) -> None:
        """run exits with error when config invalid (no credentials, not dry run)."""
        invalid_config = Config(
            binance_api_key="",
            binance_api_secret="",
            dry_run=False,
        )
        with patch("cryptex.cli.Config", return_value=invalid_config):
            result = await cli_runner.invoke(cli, ["run", "--live"])
        assert result.exit_code == 1

    @pytest.mark.asyncio
    async def test_run_dry_run_succeeds_with_mock(
        self, cli_runner: CliRunner, config: Config
    ) -> None:
        """run --dry-run succeeds with valid config and mocked pipeline."""
        with (
            patch("cryptex.cli.Config", return_value=config),
            patch("cryptex.cli.run_pipeline", new_callable=AsyncMock, return_value=0),
        ):
            result = await cli_runner.invoke(cli, ["run", "--dry-run"])
            assert result.exit_code == 0


class TestRunPipeline:
    """Tests for run_pipeline function."""

    @pytest.mark.asyncio
    async def test_run_pipeline_ping_failure(self, config: Config) -> None:
        """run_pipeline returns 1 when ping fails."""
        with patch(
            "cryptex.cli.BinanceClient",
            autospec=True,
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=False)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            exit_code = await run_pipeline(config, dry_run=True)
            assert exit_code == 1

    @pytest.mark.asyncio
    async def test_run_pipeline_success_dry_run(
        self, config: Config, sample_candles: list, mock_binance_client: AsyncMock
    ) -> None:
        """run_pipeline returns 0 on success in dry run."""
        mock_binance_client.ping = AsyncMock(return_value=True)
        mock_binance_client.get_klines = AsyncMock(
            return_value=[
                [1000000, "50000", "50100", "49900", "50050", "100"],
                [1000060, "50050", "50200", "50000", "50150", "110"],
                [1000120, "50150", "50300", "50100", "50200", "120"],
                [1000180, "50200", "50400", "50150", "50350", "130"],
                [1000240, "50350", "50500", "50300", "50400", "140"],
                [1000300, "50400", "50600", "50350", "50500", "150"],
                [1000360, "50500", "50700", "50400", "50600", "160"],
                [1000420, "50600", "50800", "50500", "50700", "170"],
                [1000480, "50700", "50900", "50600", "50800", "180"],
                [1000540, "50800", "51000", "50700", "50900", "190"],
                [1000600, "50900", "51100", "50800", "51000", "200"],
                [1000660, "51000", "51200", "50900", "51100", "210"],
                [1000720, "51100", "51300", "51000", "51200", "220"],
                [1000780, "51200", "51400", "51100", "51300", "230"],
                [1000840, "51300", "51500", "51200", "51400", "240"],
                [1000900, "51400", "51600", "51300", "51500", "250"],
                [1000960, "51500", "51700", "51400", "51600", "260"],
                [1001020, "51600", "51800", "51500", "51700", "270"],
                [1001080, "51700", "51900", "51600", "51800", "280"],
                [1001140, "51800", "52000", "51700", "51900", "290"],
            ]
        )
        mock_binance_client.get_ticker_price = AsyncMock(
            return_value={"price": "51900.00"}
        )

        with patch("cryptex.cli.BinanceClient", return_value=mock_binance_client):
            exit_code = await run_pipeline(config, dry_run=True)
            assert exit_code == 0
