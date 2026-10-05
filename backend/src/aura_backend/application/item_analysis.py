from __future__ import annotations

from asyncio import sleep
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from aura_backend.ai.canonical_text import build_canonical_embedding_text
from aura_backend.ai.contracts import (
    AIProviderError,
    EmbeddingProvider,
    EmbeddingResponseError,
    ImageInput,
    VisionAnalyzer,
    VisionResponseError,
)
from aura_backend.domain.models import ItemVisualFeaturesV1, SemanticEmbedding


class ItemAnalysisRepository(Protocol):
    """Persistence operations required by the item-analysis workflow."""

    def mark_feature_analysis_processing(self, analysis_id: UUID) -> object: ...

    def complete_feature_analysis(
        self,
        *,
        analysis_id: UUID,
        features: ItemVisualFeaturesV1,
        canonical_embedding_text: str,
        embedding: SemanticEmbedding,
    ) -> object: ...

    def fail_feature_analysis(
        self,
        *,
        analysis_id: UUID,
        error_code: str,
        error_detail: str | None = None,
    ) -> object: ...


class ItemAnalysisError(RuntimeError):
    """Base error for a failed item-analysis workflow."""


class ItemAnalysisFailed(ItemAnalysisError):
    """Raised after a failure has been recorded with a stable error code."""

    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class ItemAnalysisPersistenceError(ItemAnalysisError):
    """Raised when the workflow cannot persist a lifecycle transition."""


@dataclass(frozen=True, slots=True)
class ItemAnalysisResult:
    analysis_id: UUID
    features: ItemVisualFeaturesV1
    canonical_embedding_text: str
    embedding: SemanticEmbedding


class ItemAnalysisService:
    """Coordinate one item's vision, embedding, and persistence pipeline."""

    def __init__(
        self,
        *,
        repository: ItemAnalysisRepository,
        vision_analyzer: VisionAnalyzer,
        embedding_provider: EmbeddingProvider,
        retry_delays: tuple[float, ...] = (0.5, 1.0),
        sleeper: Callable[[float], Awaitable[None]] = sleep,
    ) -> None:
        self._repository = repository
        self._vision_analyzer = vision_analyzer
        self._embedding_provider = embedding_provider
        self._retry_delays = retry_delays
        self._sleeper = sleeper

    async def analyze(
        self,
        *,
        analysis_id: UUID,
        image: ImageInput,
    ) -> ItemAnalysisResult:
        try:
            self._repository.mark_feature_analysis_processing(analysis_id)
        except Exception as error:
            raise ItemAnalysisPersistenceError(
                "Could not start item feature analysis"
            ) from error

        try:
            features = await self._analyze_with_retries(image)
        except AIProviderError as error:
            self._record_failure(analysis_id, "VISION_ANALYSIS_FAILED", error)

        if not features.quality.usable:
            self._record_failure(analysis_id, "IMAGE_UNUSABLE")

        canonical_text = build_canonical_embedding_text(features)

        try:
            embedding = await self._embed_with_retries(canonical_text)
        except AIProviderError as error:
            self._record_failure(analysis_id, "EMBEDDING_GENERATION_FAILED", error)

        try:
            self._repository.complete_feature_analysis(
                analysis_id=analysis_id,
                features=features,
                canonical_embedding_text=canonical_text,
                embedding=embedding,
            )
        except Exception as error:
            raise ItemAnalysisPersistenceError(
                "Could not complete item feature analysis"
            ) from error

        return ItemAnalysisResult(
            analysis_id=analysis_id,
            features=features,
            canonical_embedding_text=canonical_text,
            embedding=embedding,
        )

    async def _analyze_with_retries(self, image: ImageInput) -> ItemVisualFeaturesV1:
        transient_attempt = 0
        invalid_response_attempt = 0

        while True:
            try:
                return await self._vision_analyzer.analyze(image)
            except VisionResponseError:
                if invalid_response_attempt >= 1:
                    raise
                invalid_response_attempt += 1
                await self._wait_before_retry(invalid_response_attempt - 1)
            except AIProviderError:
                if transient_attempt >= len(self._retry_delays):
                    raise
                await self._wait_before_retry(transient_attempt)
                transient_attempt += 1

    async def _embed_with_retries(self, canonical_text: str) -> SemanticEmbedding:
        transient_attempt = 0

        while True:
            try:
                return await self._embedding_provider.embed(canonical_text)
            except EmbeddingResponseError:
                raise
            except AIProviderError:
                if transient_attempt >= len(self._retry_delays):
                    raise
                await self._wait_before_retry(transient_attempt)
                transient_attempt += 1

    async def _wait_before_retry(self, delay_index: int) -> None:
        if not self._retry_delays:
            return
        delay = self._retry_delays[min(delay_index, len(self._retry_delays) - 1)]
        await self._sleeper(delay)

    def _record_failure(
        self,
        analysis_id: UUID,
        error_code: str,
        cause: Exception | None = None,
    ) -> None:
        try:
            self._repository.fail_feature_analysis(
                analysis_id=analysis_id,
                error_code=error_code,
                error_detail=type(cause).__name__ if cause is not None else None,
            )
        except Exception as persistence_error:
            raise ItemAnalysisPersistenceError(
                "Could not persist item feature analysis failure"
            ) from persistence_error

        if cause is not None:
            raise ItemAnalysisFailed(error_code) from cause
        raise ItemAnalysisFailed(error_code)
