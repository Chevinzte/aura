from uuid import uuid4

from aura_backend.application.matching import CandidateMatcher, MatchingConfigV1
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
    WeightedFeature,
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
    assert "feature representation" not in result.explanation
    assert result.explanation_version == 5
    assert "This candidate bag" in result.explanation
    assert "overall feature mix overall feature mix" not in result.explanation
    sections = result.explanation.split("\n\n")
    assert len(sections) == 4
    assert sections[0] == "Classification: Strong Fit"
    assert sections[1].startswith("Matching Evidence: ")
    assert sections[2].startswith("Contrasting Evidence: ")
    assert sections[3].startswith("Subjective Qualifier: ")


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
    assert "contrast with your profile" in result.explanation
    assert "Overall, the similarities are limited" in result.explanation


def test_weak_fit_without_major_contrast_explains_limited_overlap() -> None:
    candidate = make_candidate(colour="muted mauve", hex_value="#9A7B8F").model_copy(
        update={
            "style_traits": [
                StyleTraitObservation(value="romantic", confidence=0.9),
                StyleTraitObservation(value="sporty", confidence=0.9),
            ],
            "patterns": [
                PatternObservation(value="floral", confidence=0.9),
                PatternObservation(value="graphic", confidence=0.9),
            ],
            "materials": [
                MaterialObservation(value="leather", confidence=0.9),
                MaterialObservation(value="plastic", confidence=0.9),
            ],
        }
    )
    matcher = CandidateMatcher(
        MatchingConfigV1(strong_fit_threshold=0.95, moderate_fit_threshold=0.9)
    )

    result = matcher.compare(
        candidate_item_id=uuid4(),
        profile_id=uuid4(),
        candidate_features=candidate,
        candidate_embedding=make_embedding([0.7, 0.714]),
        profile=make_profile(),
    )

    assert result.classification == "WEAK_FIT"
    assert "limited overlap" in result.explanation


def test_matching_evidence_names_the_shared_value_not_an_unrelated_profile_value() -> None:
    profile = make_profile().model_copy(
        update={
            "shape_traits": [
                WeightedFeature(value="structured", weight=0.6),
                WeightedFeature(value="elongated", weight=0.4),
            ]
        }
    )
    candidate = make_candidate().model_copy(
        update={
            "patterns": [],
            "materials": [],
            "style_traits": [],
            "shape_traits": [ShapeTraitObservation(value="elongated", confidence=0.9)],
        }
    )

    result = CandidateMatcher().compare(
        candidate_item_id=uuid4(),
        profile_id=uuid4(),
        candidate_features=candidate,
        candidate_embedding=make_embedding([1.0, 0.0]),
        profile=profile,
    )

    shape_evidence = next(
        evidence for evidence in result.matching_evidence if evidence.dimension == "shape_detail"
    )
    assert "elongated" in shape_evidence.statement
    assert "structured" not in shape_evidence.statement


def test_pattern_material_evidence_uses_natural_dimension_wording() -> None:
    candidate = make_candidate().model_copy(
        update={
            "colours": [],
            "style_traits": [],
            "shape_traits": [],
            "decorative_details": [],
        }
    )

    result = CandidateMatcher().compare(
        candidate_item_id=uuid4(),
        profile_id=uuid4(),
        candidate_features=candidate,
        candidate_embedding=make_embedding([1.0, 0.0]),
        profile=make_profile(),
    )

    evidence = next(
        item
        for item in result.matching_evidence
        if item.dimension == "pattern_material"
    )
    assert "combines floral and leather as pattern and material features" in evidence.statement
    assert "pattern or material details" not in evidence.statement


def test_single_shape_value_uses_singular_evidence_wording() -> None:
    candidate = make_candidate().model_copy(
        update={
            "colours": [],
            "patterns": [],
            "materials": [],
            "style_traits": [],
            "decorative_details": [],
        }
    )

    result = CandidateMatcher().compare(
        candidate_item_id=uuid4(),
        profile_id=uuid4(),
        candidate_features=candidate,
        candidate_embedding=make_embedding([1.0, 0.0]),
        profile=make_profile(),
    )

    evidence = next(
        item for item in result.matching_evidence if item.dimension == "shape_detail"
    )
    assert "rounded as a shape or detail feature" in evidence.statement


def test_semantic_evidence_explains_the_combined_signal() -> None:
    candidate = make_candidate().model_copy(
        update={
            "colours": [],
            "patterns": [],
            "materials": [],
            "style_traits": [],
            "shape_traits": [],
            "decorative_details": [],
        }
    )

    result = CandidateMatcher().compare(
        candidate_item_id=uuid4(),
        profile_id=uuid4(),
        candidate_features=candidate,
        candidate_embedding=make_embedding([1.0, 0.0]),
        profile=make_profile(),
    )

    assert result.matching_evidence[0].dimension == "semantic_embedding"
    assert "combined visual features" in result.matching_evidence[0].statement
    assert "no single listed trait fully explains" in result.matching_evidence[0].statement
    assert "overall visual character" not in result.matching_evidence[0].statement
