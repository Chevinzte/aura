from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aura_backend.domain.models import ItemVisualFeaturesV1, SemanticEmbedding


class AIProviderError(RuntimeError):
    """Raised when an AI provider cannot complete a request."""


class VisionResponseError(AIProviderError):
    """Raised when vision output is absent or violates the feature contract."""


class EmbeddingResponseError(AIProviderError):
    """Raised when embedding output is absent or has an invalid vector."""


@dataclass(frozen=True, slots=True)
class ImageInput:
    """Validated image bytes ready for a vision provider."""

    data: bytes
    mime_type: str
    filename: str | None = None


class VisionAnalyzer(Protocol):
    """Extract validated visual evidence from one image."""

    async def analyze(self, image: ImageInput) -> ItemVisualFeaturesV1:
        """Return only validated ItemVisualFeaturesV1 output."""


class EmbeddingProvider(Protocol):
    """Build semantic embeddings from canonical visual-feature text."""

    async def embed(self, canonical_text: str) -> SemanticEmbedding:
        """Return an embedding with model and schema metadata."""
