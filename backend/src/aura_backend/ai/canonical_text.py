"""Deterministic canonical text for semantic feature embeddings."""

from collections.abc import Iterable

from aura_backend.domain.models import ItemVisualFeaturesV1


EMBEDDING_SCHEMA_VERSION = 1


def build_canonical_embedding_text(features: ItemVisualFeaturesV1) -> str:
    """Serialize validated visual evidence in the fixed V1 embedding format."""
    sections = [
        ("item_type", [features.item_type.value]),
        ("colours", [colour.name for colour in features.colours]),
        ("patterns", [observation.value.value for observation in features.patterns]),
        ("materials", [observation.value.value for observation in features.materials]),
        ("textures", [observation.value.value for observation in features.textures]),
        (
            "shape_traits",
            [observation.value.value for observation in features.shape_traits],
        ),
        (
            "decorative_details",
            [observation.value.value for observation in features.decorative_details],
        ),
        (
            "style_traits",
            [observation.value.value for observation in features.style_traits],
        ),
        (
            "aesthetic_signals",
            [observation.value.value for observation in features.aesthetic_signals],
        ),
    ]

    return "\n".join(
        f"{label}: {', '.join(_normalize_values(values))}"
        for label, values in sections
        if values
    )


def _normalize_values(values: Iterable[str]) -> list[str]:
    normalized_values: list[str] = []
    seen_values: set[str] = set()

    for value in values:
        normalized_value = " ".join(value.lower().replace("_", " ").split())
        if normalized_value and normalized_value not in seen_values:
            normalized_values.append(normalized_value)
            seen_values.add(normalized_value)

    return normalized_values
