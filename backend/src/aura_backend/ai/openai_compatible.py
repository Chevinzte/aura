"""OpenAI-compatible AI gateway adapters for AURA's accepted MVP models."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
from pydantic import ValidationError

from aura_backend.ai.contracts import (
    AIProviderError,
    EmbeddingProvider,
    EmbeddingResponseError,
    ImageInput,
    VisionAnalyzer,
    VisionResponseError,
)
from aura_backend.core.config import Settings
from aura_backend.domain.models import ItemVisualFeaturesV1, SemanticEmbedding


class OpenAICompatibleVisionAnalyzer(VisionAnalyzer):
    """Extract ItemVisualFeaturesV1 using a vision-capable chat-completions model."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenAICompatibleVisionAnalyzer:
        return cls(
            base_url=str(settings.ai_base_url),
            api_key=settings.ai_api_key,
            model=settings.vision_model,
            timeout_seconds=settings.ai_timeout_seconds,
        )

    async def analyze(self, image: ImageInput) -> ItemVisualFeaturesV1:
        payload = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": _vision_system_instruction(),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze the primary item in this image according to the "
                                "required JSON schema."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": _as_data_url(image)},
                        },
                    ],
                },
            ],
        }

        response_data = await self._post("/chat/completions", payload)
        content = _extract_message_content(response_data)

        try:
            return ItemVisualFeaturesV1.model_validate_json(content)
        except ValidationError as error:
            raise VisionResponseError("Vision response does not match ItemVisualFeaturesV1") from error

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "aura-fastapi-backend/0.1",
        }
        timeout = httpx.Timeout(self._timeout_seconds)

        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(f"{self._base_url}{path}", json=payload)
                response.raise_for_status()
                response_data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise AIProviderError("Vision request to AI gateway failed") from error

        if not isinstance(response_data, dict):
            raise VisionResponseError("Vision response must be a JSON object")
        return response_data


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Create semantic embeddings through an OpenAI-compatible embeddings endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        schema_version: int,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._schema_version = schema_version
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenAICompatibleEmbeddingProvider:
        return cls(
            base_url=str(settings.ai_base_url),
            api_key=settings.ai_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            schema_version=1,
            timeout_seconds=settings.ai_timeout_seconds,
        )

    async def embed(self, canonical_text: str) -> SemanticEmbedding:
        if not canonical_text.strip():
            raise ValueError("canonical_text must not be empty")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "aura-fastapi-backend/0.1",
        }
        timeout = httpx.Timeout(self._timeout_seconds)

        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._base_url}/embeddings",
                    json={"model": self._model, "input": canonical_text},
                )
                response.raise_for_status()
                response_data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise AIProviderError("Embedding request to AI gateway failed") from error

        values = _extract_embedding_values(response_data)
        if len(values) != self._dimensions:
            raise EmbeddingResponseError(
                "Embedding dimension does not match configured dimensions"
            )

        return SemanticEmbedding(
            provider="ai_lodge",
            model=self._model,
            dimensions=self._dimensions,
            schema_version=self._schema_version,
            values=values,
        )


def _vision_system_instruction() -> str:
    schema = ItemVisualFeaturesV1.model_json_schema(by_alias=True)
    return "\n".join(
        [
            "You are AURA's visual feature extraction service.",
            "Return one JSON object only; do not include markdown or commentary.",
            "Analyze visual evidence only. Do not judge aesthetic compatibility.",
            "Use only the enum values defined in the schema.",
            "Use empty lists when an optional feature is not visible.",
            "For an unusable image, set quality.usable to false, use itemType.value",
            "as 'unknown', use an empty colours list, and explain the limitation",
            "in the neutral description and observations.",
            "Required JSON schema:",
            json.dumps(schema, separators=(",", ":")),
        ]
    )


def _as_data_url(image: ImageInput) -> str:
    encoded_image = base64.b64encode(image.data).decode("ascii")
    return f"data:{image.mime_type};base64,{encoded_image}"


def _extract_message_content(response_data: dict[str, Any]) -> str:
    try:
        content = response_data["choices"][0]["message"]["content"]
    except (IndexError, KeyError, TypeError) as error:
        raise VisionResponseError("Vision response has no message content") from error

    if not isinstance(content, str) or not content.strip():
        raise VisionResponseError("Vision response content must be a non-empty string")
    return content


def _extract_embedding_values(response_data: Any) -> list[float]:
    try:
        values = response_data["data"][0]["embedding"]
    except (IndexError, KeyError, TypeError) as error:
        raise EmbeddingResponseError("Embedding response has no vector") from error

    if not isinstance(values, list) or not all(
        isinstance(value, int | float) for value in values
    ):
        raise EmbeddingResponseError("Embedding vector must contain only numbers")
    return [float(value) for value in values]
