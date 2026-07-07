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

    @model_validator(mode="after")
    def enforce_mvp_safety(self) -> Self:
        if self.enable_live_actions:
            raise ValueError("live actions must remain disabled for the MVP")
        return self


settings = Settings()
