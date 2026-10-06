from uuid import uuid4

from aura_backend.application.matching import CandidateMatcher
from aura_backend.domain.models import (
    AestheticProfileV1,
    ColourObservation,
    DecorativeDetailObservation,
    ImageQuality,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    MaterialObservation,
    PatternObservation,
    SemanticEmbedding,
    ShapeTraitObservation,
    StyleTraitObservation,
)


def make_embedding(values: list[float]) -> SemanticEmbedding:
    return SemanticEmbedding(
        provider="test",
        model="embedding-v1",
        dimensions=2,
        schema_version=1,
        values=values,
    )


def make_profile(*, colour_diversity: float = 0.3) -> AestheticProfileV1:
    return AestheticProfileV1(
        user_id=uuid4(),
        colours=[
            {"name": "blush pink", "hex": "#E8B4B8", "weight": 0.7},
            {"name": "cream", "hex": "#FFFDD0", "weight": 0.3},
        ],
        patterns=[{"value": "floral", "weight": 1.0}],
        materials=[{"value": "leather", "weight": 1.0}],
        shape_traits=[{"value": "rounded", "weight": 1.0}],
        decorative_details=[{"value": "gold_tone_hardware", "weight": 1.0}],
        style_traits=[
            {"value": "romantic", "weight": 0.6},
            {"value": "delicate", "weight": 0.4},
        ],
        embedding_centroid=make_embedding([1.0, 0.0]),
        colour_diversity=colour_diversity,
        style_diversity=0.6,
        contributing_feature_ids=[uuid4() for _ in range(5)],
        summary="A soft romantic profile.",
        algorithm_version=1,
    )


def make_candidate(*, colour: str = "blush pink", hex_value: str = "#E8B4B8") -> ItemVisualFeaturesV1:
    return ItemVisualFeaturesV1(
        item_type=ItemTypeObservation(value="handbag", confidence=0.95),
        item_name="candidate bag",
        colours=[
            ColourObservation(
                name=colour,
                hex=hex_value,
                proportion=1.0,
                confidence=0.95,
            )
        ],
        patterns=[PatternObservation(value="floral", confidence=0.9)],
        materials=[MaterialObservation(value="leather", confidence=0.9)],
        shape_traits=[ShapeTraitObservation(value="rounded", confidence=0.9)],
        decorative_details=[
            DecorativeDetailObservation(value="gold_tone_hardware", confidence=0.9)
        ],
        style_traits=[StyleTraitObservation(value="romantic", confidence=0.9)],
        quality=ImageQuality(usable=True, score=0.95),
        description="A candidate handbag.",
    )


def test_matching_candidate_is_classified_as_strong_fit() -> None:
    result = CandidateMatcher().compare(
        candidate_item_id=uuid4(),
        profile_id=uuid4(),
        candidate_features=make_candidate(),
        candidate_embedding=make_embedding([1.0, 0.0]),
        profile=make_profile(),
    )

    assert result.classification == "STRONG_FIT"
    assert result.overall_score >= 0.78
    assert len(result.matching_evidence) == 2
    assert "subjective guidance" in result.explanation


def test_single_colour_difference_can_be_intentional_contrast() -> None:
    result = CandidateMatcher().compare(
        candidate_item_id=uuid4(),
        profile_id=uuid4(),
        candidate_features=make_candidate(colour="navy", hex_value="#000080"),
        candidate_embedding=make_embedding([1.0, 0.0]),
        profile=make_profile(colour_diversity=0.7),
    )

    assert result.classification == "INTENTIONAL_CONTRAST"
    assert result.contrasting_evidence[0].dimension == "colour"


def test_multiple_differences_are_not_intentional_contrast() -> None:
    candidate = make_candidate(colour="navy", hex_value="#000080").model_copy(
        update={
            "style_traits": [StyleTraitObservation(value="sporty", confidence=0.9)],
            "patterns": [PatternObservation(value="graphic", confidence=0.9)],
            "materials": [MaterialObservation(value="plastic", confidence=0.9)],
        }
    )
    result = CandidateMatcher().compare(
        candidate_item_id=uuid4(),
        profile_id=uuid4(),
        candidate_features=candidate,
        candidate_embedding=make_embedding([0.0, 1.0]),
        profile=make_profile(colour_diversity=0.7),
    )

    assert result.classification == "WEAK_FIT"
