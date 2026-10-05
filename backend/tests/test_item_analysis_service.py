from __future__ import annotations

from asyncio import run
from uuid import UUID, uuid4

import pytest

from aura_backend.ai.contracts import AIProviderError, ImageInput
from aura_backend.application.item_analysis import ItemAnalysisFailed, ItemAnalysisService
from aura_backend.domain.models import (
    ColourObservation,
    ImageQuality,
    ImageQualityWarning,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    SemanticEmbedding,
)


class FakeRepository:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def mark_feature_analysis_processing(self, analysis_id: UUID) -> object:
        self.events.append(("processing", analysis_id))
        return {}

    def complete_feature_analysis(self, **values: object) -> object:
        self.events.append(("completed", values))
        return {}

    def fail_feature_analysis(self, **values: object) -> object:
        self.events.append(("failed", values))
        return {}


class StaticVisionAnalyzer:
    def __init__(self, features: ItemVisualFeaturesV1) -> None:
        self.features = features
        self.calls = 0

    async def analyze(self, _: ImageInput) -> ItemVisualFeaturesV1:
        self.calls += 1
        return self.features


class FlakyVisionAnalyzer(StaticVisionAnalyzer):
    async def analyze(self, image: ImageInput) -> ItemVisualFeaturesV1:
        self.calls += 1
        if self.calls == 1:
            raise AIProviderError("temporary failure")
        return self.features


class StaticEmbeddingProvider:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    async def embed(self, canonical_text: str) -> SemanticEmbedding:
        self.inputs.append(canonical_text)
        return SemanticEmbedding(
            provider="test",
            model="test-embedding",
            dimensions=2,
            schema_version=1,
            values=[0.2, 0.8],
        )


def make_usable_features() -> ItemVisualFeaturesV1:
    return ItemVisualFeaturesV1(
        item_type=ItemTypeObservation(value="handbag", confidence=0.95),
        item_name="blush pink handbag",
        colours=[
            ColourObservation(
                name="blush pink",
                hex="#D9A6AA",
                proportion=1.0,
                confidence=0.9,
            )
        ],
        quality=ImageQuality(usable=True, score=0.95),
        description="A blush pink handbag.",
    )


def make_unusable_features() -> ItemVisualFeaturesV1:
    return ItemVisualFeaturesV1(
        item_type=ItemTypeObservation(value="unknown", confidence=0.1),
        item_name="unknown item",
        colours=[],
        quality=ImageQuality(
            usable=False,
            score=0.1,
            warnings=[ImageQualityWarning.NO_CLEAR_PRIMARY_ITEM],
        ),
        observations=["No clear primary item is visible."],
        description="The image does not contain a clear primary item.",
    )


def test_item_analysis_completes_all_pipeline_stages() -> None:
    repository = FakeRepository()
    embedding_provider = StaticEmbeddingProvider()
    service = ItemAnalysisService(
        repository=repository,
        vision_analyzer=StaticVisionAnalyzer(make_usable_features()),
        embedding_provider=embedding_provider,
        retry_delays=(),
    )

    result = run(
        service.analyze(
            analysis_id=uuid4(),
            image=ImageInput(data=b"image", mime_type="image/png"),
        )
    )

    assert result.features.item_type.value == "handbag"
    assert embedding_provider.inputs == ["item_type: handbag\ncolours: blush pink"]
    assert [event[0] for event in repository.events] == ["processing", "completed"]


def test_item_analysis_retries_a_transient_vision_failure() -> None:
    repository = FakeRepository()
    vision_analyzer = FlakyVisionAnalyzer(make_usable_features())
    service = ItemAnalysisService(
        repository=repository,
        vision_analyzer=vision_analyzer,
        embedding_provider=StaticEmbeddingProvider(),
        retry_delays=(0,),
    )

    run(
        service.analyze(
            analysis_id=uuid4(),
            image=ImageInput(data=b"image", mime_type="image/png"),
        )
    )

    assert vision_analyzer.calls == 2


def test_item_analysis_records_unusable_image_without_embedding() -> None:
    repository = FakeRepository()
    embedding_provider = StaticEmbeddingProvider()
    service = ItemAnalysisService(
        repository=repository,
        vision_analyzer=StaticVisionAnalyzer(make_unusable_features()),
        embedding_provider=embedding_provider,
        retry_delays=(),
    )

    with pytest.raises(ItemAnalysisFailed) as error:
        run(
            service.analyze(
                analysis_id=uuid4(),
                image=ImageInput(data=b"image", mime_type="image/png"),
            )
        )

    assert error.value.error_code == "IMAGE_UNUSABLE"
    assert embedding_provider.inputs == []
    assert [event[0] for event in repository.events] == ["processing", "failed"]
