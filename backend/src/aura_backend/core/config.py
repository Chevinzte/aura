from functools import lru_cache
from typing import Literal

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
    internal_api_key: str = Field(
        validation_alias="AURA_INTERNAL_API_KEY",
        min_length=32,
    )
    ai_base_url: AnyHttpUrl = Field(validation_alias="AURA_AI_BASE_URL")
    ai_api_key: str = Field(validation_alias="AURA_AI_API_KEY")
    ai_timeout_seconds: float = Field(
        default=45.0,
        validation_alias="AURA_AI_TIMEOUT_SECONDS",
        gt=0,
        le=120,
    )
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
    max_image_bytes: int = Field(
        default=10 * 1024 * 1024,
        validation_alias="AURA_MAX_IMAGE_BYTES",
        ge=1,
    )
    min_image_dimension: int = Field(
        default=256,
        validation_alias="AURA_MIN_IMAGE_DIMENSION",
        ge=1,
    )
    openai_image_base_url: AnyHttpUrl = Field(
        default="https://api.openai.com/v1",
        validation_alias="OPENAI_IMAGE_BASE_URL",
    )
    openai_image_api_key: str | None = Field(
        default=None,
        validation_alias="OPENAI_IMAGE_API_KEY",
    )
    openai_image_model: str = Field(
        default="gpt-image-2.5-flare",
        validation_alias="OPENAI_IMAGE_MODEL",
    )
    openai_image_timeout_seconds: float = Field(
        default=300.0,
        validation_alias="OPENAI_IMAGE_TIMEOUT_SECONDS",
        gt=0,
        le=600,
    )
    openai_image_quality: Literal["low", "medium", "high"] = Field(
        default="low",
        validation_alias="OPENAI_IMAGE_QUALITY",
    )
    openai_image_size: str = Field(
        default="1024x1024",
        validation_alias="OPENAI_IMAGE_SIZE",
        pattern=r"^\d+x\d+$",
    )


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance per process."""
    return Settings()
