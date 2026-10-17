"""Direct OpenAI Images API adapter for optional AURA reference images."""

from __future__ import annotations

import base64
import binascii
from typing import Any

import httpx

from aura_backend.ai.contracts import GeneratedImage, ImageGenerationError, ImageGenerator
from aura_backend.core.config import Settings


class OpenAIImageGenerator(ImageGenerator):
    """Generate one product-style reference image through the OpenAI Images API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_seconds: float,
        quality: str,
        size: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or ""
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._quality = quality
        self._size = size
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenAIImageGenerator:
        return cls(
            base_url=str(settings.openai_image_base_url),
            api_key=settings.openai_image_api_key,
            model=settings.openai_image_model,
            timeout_seconds=settings.openai_image_timeout_seconds,
            quality=settings.openai_image_quality,
            size=settings.openai_image_size,
        )

    async def generate(self, prompt: str) -> GeneratedImage:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        if not self._api_key:
            raise ImageGenerationError("OpenAI image generation is not configured")

        payload = {
            "model": self._model,
            "prompt": prompt,
            "n": 1,
            "size": self._size,
            "quality": self._quality,
            "background": "opaque",
            "output_format": "jpeg",
            "output_compression": 82,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "aura-fastapi-backend/0.1",
        }

        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(self._timeout_seconds),
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._base_url}/images/generations",
                    json=payload,
                )
                response.raise_for_status()
                response_data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ImageGenerationError("OpenAI image request failed") from error

        encoded_image = _extract_base64_image(response_data)
        try:
            image_data = base64.b64decode(encoded_image, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ImageGenerationError("OpenAI returned invalid image data") from error
        if not image_data:
            raise ImageGenerationError("OpenAI returned an empty image")
        return GeneratedImage(data=image_data, mime_type="image/jpeg")


def _extract_base64_image(response_data: Any) -> str:
    try:
        encoded_image = response_data["data"][0]["b64_json"]
    except (IndexError, KeyError, TypeError) as error:
        raise ImageGenerationError("OpenAI response has no generated image") from error
    if not isinstance(encoded_image, str) or not encoded_image.strip():
        raise ImageGenerationError("OpenAI response image must be base64 text")
    if encoded_image.startswith("data:"):
        try:
            encoded_image = encoded_image.split(",", 1)[1]
        except IndexError as error:
            raise ImageGenerationError("OpenAI returned an invalid data URL") from error
    return encoded_image
