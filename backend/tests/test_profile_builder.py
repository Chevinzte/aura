from math import isclose, sqrt
from uuid import uuid4

import pytest

from aura_backend.application.profiles import (
    AestheticProfileBuilder,
    ProfileBuildError,
    ProfileInput,
    ProfileService,
)
from aura_backend.repositories.supabase import FeaturePipelineVersion
from aura_backend.domain.models import (
    ColourObservation,
    ImageQuality,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    SemanticEmbedding,
    StyleTraitObservation,
)


def make_input(
    *,
    colour: str,
    hex_value: str,
    style: str,
    embedding: list[float],
    content_hash: str | None = None,
) -> ProfileInput:
    feature_id = uuid4()
    return ProfileInput(
        feature_id=feature_id,
        content_sha256=content_hash or feature_id.hex * 2,
        features=ItemVisualFeaturesV1(
            item_type=ItemTypeObservation(value="handbag", confidence=0.9),
            item_name="bag",
            colours=[
                ColourObservation(
                    name=colour,
                    hex=hex_value,
                    proportion=1.0,
                    confidence=1.0,
                )
            ],
            style_traits=[StyleTraitObservation(value=style, confidence=1.0)],
            quality=ImageQuality(usable=True, score=1.0),
            description="A bag.",
        ),
        embedding=SemanticEmbedding(
            provider="test",
            model="embedding-v1",
            dimensions=2,
            schema_version=1,
            values=embedding,
        ),
    )


def test_profile_builder_aggregates_distributions_and_normalizes_centroid() -> None:
    inputs = [
        make_input(colour="pink", hex_value="#FFC0CB", style="romantic", embedding=[1, 0]),
        make_input(colour="pink", hex_value="#FFC0CB", style="romantic", embedding=[1, 0]),
        make_input(colour="cream", hex_value="#FFFDD0", style="delicate", embedding=[0, 1]),
        make_input(colour="cream", hex_value="#FFFDD0", style="delicate", embedding=[0, 1]),
        make_input(colour="navy", hex_value="#000080", style="classic", embedding=[1, 1]),
    ]

    built = AestheticProfileBuilder().build(user_id=uuid4(), inputs=inputs)

    assert len(built.profile.contributing_feature_ids) == 5
    assert isclose(sum(colour.weight for colour in built.profile.colours), 1.0)
    assert isclose(sum(style.weight for style in built.profile.style_traits), 1.0)
    centroid = built.profile.embedding_centroid.values
    assert isclose(sqrt(sum(value * value for value in centroid)), 1.0)
    assert "pink" in built.profile.summary
    assert built.profile.colour_diversity > 0


def test_exact_duplicates_share_one_items_influence() -> None:
    duplicate_hash = "a" * 64
    inputs = [
        make_input(
            colour="pink",
            hex_value="#FFC0CB",
            style="romantic",
            embedding=[1, 0],
            content_hash=duplicate_hash,
        ),
        make_input(
            colour="pink",
            hex_value="#FFC0CB",
            style="romantic",
            embedding=[1, 0],
            content_hash=duplicate_hash,
        ),
        make_input(colour="cream", hex_value="#FFFDD0", style="delicate", embedding=[0, 1]),
        make_input(colour="navy", hex_value="#000080", style="classic", embedding=[1, 1]),
        make_input(colour="black", hex_value="#000000", style="minimal", embedding=[-1, 1]),
    ]

    built = AestheticProfileBuilder().build(user_id=uuid4(), inputs=inputs)

    duplicate_weights = [built.effective_weights[item.feature_id] for item in inputs[:2]]
    unique_weight = built.effective_weights[inputs[2].feature_id]
    assert isclose(sum(duplicate_weights), unique_weight)


def test_profile_builder_requires_five_compatible_items() -> None:
    item = make_input(colour="pink", hex_value="#FFC0CB", style="romantic", embedding=[1, 0])
    with pytest.raises(ProfileBuildError, match="five"):
        AestheticProfileBuilder().build(user_id=uuid4(), inputs=[item] * 4)

    incompatible = [
        make_input(colour="pink", hex_value="#FFC0CB", style="romantic", embedding=[1, 0])
        for _ in range(5)
    ]
    incompatible[-1] = ProfileInput(
        feature_id=incompatible[-1].feature_id,
        content_sha256=incompatible[-1].content_sha256,
        features=incompatible[-1].features,
        embedding=SemanticEmbedding(
            provider="other",
            model="embedding-v1",
            dimensions=2,
            schema_version=1,
            values=[1, 0],
        ),
    )
    with pytest.raises(ProfileBuildError, match="incompatible"):
        AestheticProfileBuilder().build(user_id=uuid4(), inputs=incompatible)


class FakeProfileRepository:
    def __init__(self, inputs: list[ProfileInput]) -> None:
        self.inputs = inputs
        self.activated = False

    def list_profile_inputs(self, **_: object) -> list[ProfileInput]:
        return self.inputs

    def activate_profile(self, **_: object) -> object:
        self.activated = True
        return {}


def make_pipeline() -> FeaturePipelineVersion:
    return FeaturePipelineVersion(
        vision_provider="gateway",
        vision_model="vision-model",
        vision_prompt_version=1,
        feature_schema_version=1,
        embedding_provider="test",
        embedding_model="embedding-v1",
        embedding_dimensions=2,
        embedding_schema_version=1,
    )


def test_profile_service_collects_until_five_then_activates() -> None:
    inputs = [
        make_input(colour="pink", hex_value="#FFC0CB", style="romantic", embedding=[1, 0])
        for _ in range(5)
    ]
    collecting_repository = FakeProfileRepository(inputs[:4])
    collecting_service = ProfileService(
        repository=collecting_repository,
        builder=AestheticProfileBuilder(),
        pipeline=make_pipeline(),
    )
    assert collecting_service.rebuild_if_ready(uuid4()).status == "COLLECTING"
    assert collecting_repository.activated is False

    ready_repository = FakeProfileRepository(inputs)
    ready_service = ProfileService(
        repository=ready_repository,
        builder=AestheticProfileBuilder(),
        pipeline=make_pipeline(),
    )
    assert ready_service.rebuild_if_ready(uuid4()).status == "READY"
    assert ready_repository.activated is True
