"""Configuration management for the trading pipeline."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from project root (when developing) or cwd (when installed)
def _load_env_files() -> None:
    cwd = Path.cwd()
    project_root = Path(__file__).resolve().parent.parent
    for base in (cwd, project_root):
        env_default = base / ".env.default"
        env_file = base / ".env"
        if env_default.exists():
            load_dotenv(env_default)
        if env_file.exists():
            load_dotenv(env_file)
            break


_load_env_files()


class Config(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_case=True,
    )

    # Exchange
    binance_api_key: str = Field(default="")
    binance_api_secret: str = Field(default="")
    binance_base_url: str = Field(
        default="https://testnet.binance.vision/api",
    )
    use_testnet: bool = Field(default=True)

    # Trading
    symbol: str = Field(default="BTCUSDT")
    timeframe: str = Field(default="5m")
    position_size: float = Field(default=0.001, gt=0)
    order_type: str = Field(default="MARKET")

    # Strategy
    ma_period: int = Field(default=20, ge=2)

    # Data storage
    data_cache_ttl_seconds: int = Field(default=30)

    # Execution mode
    dry_run: bool = Field(default=False)

    def validate(self) -> list[str]:
        """Validate configuration and return list of error messages."""
        errors = []
        if not self.dry_run:
            if not self.binance_api_key:
                errors.append(
                    "BINANCE_API_KEY is required (set DRY_RUN=true to simulate)"
                )
            if not self.binance_api_secret:
                errors.append(
                    "BINANCE_API_SECRET is required (set DRY_RUN=true to simulate)"
                )
        return errors
