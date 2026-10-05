from aura_backend.ai.canonical_text import build_canonical_embedding_text
from aura_backend.domain.models import (
    AestheticSignalObservation,
    AestheticSignalValue,
    ColourObservation,
    ImageQuality,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    MaterialObservation,
    MaterialValue,
    PatternObservation,
    PatternValue,
    StyleTraitObservation,
    StyleTraitValue,
)


def test_canonical_text_uses_only_normalized_validated_features() -> None:
    features = ItemVisualFeaturesV1(
        item_type=ItemTypeObservation(value=" Handbag ", confidence=0.98),
        item_name="Floral handbag",
        colours=[
            ColourObservation(
                name="Blush Pink",
                hex="#D9A6AA",
                proportion=0.6,
                confidence=0.91,
            ),
            ColourObservation(
                name="blush pink",
                hex="#D9A6AA",
                proportion=0.4,
                confidence=0.85,
            ),
        ],
        patterns=[PatternObservation(value=PatternValue.FLORAL, confidence=0.9)],
        materials=[MaterialObservation(value=MaterialValue.LEATHER, confidence=0.8)],
        style_traits=[
            StyleTraitObservation(value=StyleTraitValue.DELICATE, confidence=0.9),
            StyleTraitObservation(value=StyleTraitValue.ROMANTIC, confidence=0.8),
        ],
        aesthetic_signals=[
            AestheticSignalObservation(
                value=AestheticSignalValue.SOFT_FEMININE,
                confidence=0.7,
            )
        ],
        quality=ImageQuality(usable=True, score=0.9),
        observations=["The bag is photographed on a table."],
        description="A floral blush pink handbag.",
    )

    assert build_canonical_embedding_text(features) == (
        "item_type: handbag\n"
        "colours: blush pink\n"
        "patterns: floral\n"
        "materials: leather\n"
        "style_traits: delicate, romantic\n"
        "aesthetic_signals: soft feminine"
    )
