from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "dumpectorist"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8787, ge=1, le=65535)
    database_url: str = "postgresql+asyncpg://app:change_me@postgres:5432/app"
    redis_url: str = "redis://redis:6379/0"
    telegram_bot_token: str = "change_me"
    telegram_admin_ids: str = ""
    enable_live_actions: bool = False
    max_leverage: int = Field(default=5, ge=1, le=5)

    worker_tick_seconds: float = Field(default=1.0, gt=0, le=60)
    worker_source_timeout_seconds: float = Field(default=8.0, gt=0, le=120)
    worker_execution_interval_seconds: float = Field(default=5.0, gt=0, le=3600)
    worker_benchmark_interval_seconds: float = Field(default=10.0, gt=0, le=3600)
    worker_ohlcv_interval_seconds: float = Field(default=300.0, gt=0, le=86400)
    worker_discovery_interval_seconds: float = Field(default=300.0, gt=0, le=86400)
    worker_cleanup_interval_seconds: float = Field(default=3600.0, gt=0, le=86400)
    worker_retention_days: int = Field(default=30, ge=1, le=3650)
    worker_failure_alert_threshold: int = Field(default=3, ge=1, le=100)

    worker_enable_lbank: bool = True
    worker_enable_benchmarks: bool = True
    worker_enable_ohlcv: bool = True
    worker_enable_discovery: bool = True
    worker_lbank_symbol: str = "BTCUSDT"
    worker_mexc_symbol: str = "BTC_USDT"
    worker_gate_symbol: str = "BTC_USDT"
    worker_bybit_symbol: str = "BTCUSDT"
    worker_binance_symbol: str = "BTCUSDT"
    worker_ohlcv_symbol: str = "BTCUSDT"
    worker_ohlcv_limit: int = Field(default=200, ge=2, le=1000)

    @model_validator(mode="after")
    def enforce_mvp_safety(self) -> Self:
        if self.enable_live_actions:
            raise ValueError("live actions must remain disabled for the MVP")

        normalized_env = self.app_env.strip().lower()
        if normalized_env in {"production", "prod"} and "change_me" in self.database_url:
            raise ValueError("production database credentials must not use change_me")

        required_symbols: dict[str, str] = {}
        if self.worker_enable_lbank:
            required_symbols["worker_lbank_symbol"] = self.worker_lbank_symbol
        if self.worker_enable_benchmarks:
            required_symbols.update(
                {
                    "worker_mexc_symbol": self.worker_mexc_symbol,
                    "worker_gate_symbol": self.worker_gate_symbol,
                    "worker_bybit_symbol": self.worker_bybit_symbol,
                    "worker_binance_symbol": self.worker_binance_symbol,
                }
            )
        if self.worker_enable_ohlcv:
            required_symbols["worker_ohlcv_symbol"] = self.worker_ohlcv_symbol
        for name, value in required_symbols.items():
            if not value.strip():
                raise ValueError(f"{name} must not be blank")
        return self


settings = Settings()
