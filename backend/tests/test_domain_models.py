from uuid import uuid4

import pytest
from pydantic import ValidationError

from aura_backend.domain.models import (
    AestheticProfileV1,
    ColourObservation,
    ImageQuality,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    SemanticEmbedding,
)


def make_embedding() -> SemanticEmbedding:
    return SemanticEmbedding(
        provider="test-provider",
        model="test-model",
        dimensions=2,
        schema_version=1,
        values=[0.2, 0.8],
    )


def make_features() -> ItemVisualFeaturesV1:
    return ItemVisualFeaturesV1(
        item_type=ItemTypeObservation(value="handbag", confidence=0.98),
        item_name="floral handbag",
        colours=[
            ColourObservation(
                name="blush pink",
                hex="#D9A6AA",
                proportion=0.6,
                confidence=0.91,
            ),
            ColourObservation(
                name="cream",
                hex="#FFF8E7",
                proportion=0.4,
                confidence=0.87,
            ),
        ],
        quality=ImageQuality(usable=True, score=0.9),
        description="A compact blush pink handbag.",
    )


def test_item_visual_features_accepts_usable_valid_evidence() -> None:
    features = make_features()
    provider_payload = features.model_dump(by_alias=True)
    parsed_features = ItemVisualFeaturesV1.model_validate(provider_payload)

    assert features.schema_version == 1
    assert provider_payload["itemType"]["value"] == "handbag"
    assert parsed_features == features


def test_item_visual_features_rejects_invalid_colour_proportions() -> None:
    with pytest.raises(ValidationError, match="colour proportions"):
        ItemVisualFeaturesV1(
            item_type=ItemTypeObservation(value="wallet", confidence=0.9),
            item_name="wallet",
            colours=[
                ColourObservation(
                    name="navy",
                    hex="#000080",
                    proportion=0.5,
                    confidence=0.9,
                )
            ],
            quality=ImageQuality(usable=True, score=0.9),
            description="A navy wallet.",
        )


def test_embedding_rejects_value_count_that_differs_from_dimensions() -> None:
    with pytest.raises(ValidationError, match="value count"):
        SemanticEmbedding(
            provider="test-provider",
            model="test-model",
            dimensions=3,
            schema_version=1,
            values=[0.1, 0.2],
        )


def test_profile_requires_at_least_five_feature_records() -> None:
    with pytest.raises(ValidationError, match="contributing_feature_ids"):
        AestheticProfileV1(
            user_id=uuid4(),
            colours=[{"name": "cream", "hex": "#FFF8E7", "weight": 1.0}],
            embedding_centroid=make_embedding(),
            colour_diversity=0.3,
            style_diversity=0.2,
            contributing_feature_ids=[uuid4()],
            summary="A soft neutral profile.",
            algorithm_version=1,
        )
