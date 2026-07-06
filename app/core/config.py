from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "dumpectorist"
    api_host: str = "0.0.0.0"
    api_port: int = 8787
    database_url: str = "postgresql+asyncpg://app:change_me@postgres:5432/app"
    redis_url: str = "redis://redis:6379/0"
    telegram_bot_token: str = "change_me"
    telegram_admin_ids: str = ""
    enable_live_actions: bool = False
    max_leverage: int = 5

    def validate(self) -> None:
        checks = [not self.enable_live_actions, self.max_leverage <= 5]
        if not all(checks):
            raise ValueError("invalid MVP settings")


settings = Settings()
settings.validate()
