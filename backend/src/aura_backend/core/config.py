from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: AnyHttpUrl = Field(validation_alias="SUPABASE_URL")
    supabase_secret_key: str = Field(validation_alias="SUPABASE_SECRET_KEY")
    vision_model: str = Field(
        default="gemini-3.5-flash-lite",
        validation_alias="AURA_VISION_MODEL",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias="AURA_EMBEDDING_MODEL",
    )
    embedding_dimensions: int = Field(
        default=1536,
        validation_alias="AURA_EMBEDDING_DIMENSIONS",
        ge=1,
    )


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance per process."""
    return Settings()
