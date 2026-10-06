from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Telegram adapter configuration loaded from the repository environment."""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(validation_alias="TELEGRAM_BOT_TOKEN")
    backend_url: AnyHttpUrl = Field(
        default="http://127.0.0.1:8000",
        validation_alias="AURA_BACKEND_URL",
    )
    backend_timeout_seconds: float = Field(
        default=120.0,
        validation_alias="AURA_BACKEND_TIMEOUT_SECONDS",
        gt=0,
        le=300,
    )


@lru_cache
def get_bot_settings() -> BotSettings:
    return BotSettings()
