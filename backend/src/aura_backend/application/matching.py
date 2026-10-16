from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from uuid import UUID

from aura_backend.domain.models import (
    AestheticProfileV1,
    ItemVisualFeaturesV1,
    MatchClassification,
    MatchComponentScore,
    MatchDimension,
    MatchEvidence,
    MatchResultV1,
    SemanticEmbedding,
    WeightedFeature,
)


class MatchBuildError(ValueError):
    """Raised when candidate and profile representations are incompatible."""


@dataclass(frozen=True, slots=True)
class ActiveProfile:
    profile_id: UUID
    profile: AestheticProfileV1
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MatchingConfigV1:
    colour_weight: float = 0.30
    style_weight: float = 0.25
    pattern_material_weight: float = 0.15
    shape_detail_weight: float = 0.10
    semantic_embedding_weight: float = 0.20
    strong_fit_threshold: float = 0.78
    moderate_fit_threshold: float = 0.58
    intentional_match_threshold: float = 0.72
    intentional_contrast_threshold: float = 0.35
    diversity_threshold: float = 0.45


@dataclass(frozen=True, slots=True)
class _Component:
    dimension: MatchDimension
    score: float
    confidence: float
    candidate_values: list[str]
    profile_values: list[str]
    matching_values: list[str]
    contrasting_values: list[str]


class CandidateMatcher:
    """Compare candidate evidence with one immutable profile snapshot."""

    scoring_version = 1
    explanation_version = 3

    def __init__(self, config: MatchingConfigV1 | None = None) -> None:
        self._config = config or MatchingConfigV1()

    def compare(
        self,
        *,
        candidate_item_id: UUID,
        profile_id: UUID,
        candidate_features: ItemVisualFeaturesV1,
        candidate_embedding: SemanticEmbedding,
        profile: AestheticProfileV1,
    ) -> MatchResultV1:
        self._ensure_compatible_embeddings(candidate_embedding, profile.embedding_centroid)
        components = self._components(
            candidate_features,
            candidate_embedding,
            profile,
        )
        if not components:
            raise MatchBuildError("No supported matching components are available")

        base_weights = {
            MatchDimension.COLOUR: self._config.colour_weight,
            MatchDimension.STYLE: self._config.style_weight,
            MatchDimension.PATTERN_MATERIAL: self._config.pattern_material_weight,
            MatchDimension.SHAPE_DETAIL: self._config.shape_detail_weight,
            MatchDimension.SEMANTIC_EMBEDDING: self._config.semantic_embedding_weight,
        }
        raw_weights = {
            component.dimension: base_weights[component.dimension] * component.confidence
            for component in components
        }
        total_raw_weight = sum(raw_weights.values())
        if total_raw_weight <= 0:
            raise MatchBuildError("Candidate evidence has no usable confidence")

        component_scores = [
            MatchComponentScore(
                dimension=component.dimension,
                score=component.score,
                effective_weight=raw_weights[component.dimension] / total_raw_weight,
                confidence=component.confidence,
            )
            for component in components
        ]
        overall_score = sum(
            component.score * score.effective_weight
            for component, score in zip(components, component_scores, strict=True)
        )
        classification = self._classify(
            overall_score=overall_score,
            components=components,
            profile=profile,
        )
        matching_evidence, contrasting_evidence = self._evidence(
            components,
            classification,
        )
        explanation = self._explanation(
            classification,
            matching_evidence,
            contrasting_evidence,
        )
        return MatchResultV1(
            candidate_item_id=candidate_item_id,
            profile_id=profile_id,
            overall_score=overall_score,
            classification=classification,
            component_scores=component_scores,
            matching_evidence=matching_evidence,
            contrasting_evidence=contrasting_evidence,
            explanation=explanation,
            scoring_version=self.scoring_version,
            explanation_version=self.explanation_version,
        )

    def _components(
        self,
        features: ItemVisualFeaturesV1,
        embedding: SemanticEmbedding,
        profile: AestheticProfileV1,
    ) -> list[_Component]:
        components: list[_Component] = []
        colour = self._colour_component(features, profile)
        if colour is not None:
            components.append(colour)
        style = self._categorical_component(
            MatchDimension.STYLE,
            [(str(value.value), value.confidence) for value in features.style_traits],
            profile.style_traits,
            features.quality.score,
        )
        if style is not None:
            components.append(style)
        pattern_material = self._categorical_component(
            MatchDimension.PATTERN_MATERIAL,
            [
                *((str(value.value), value.confidence) for value in features.patterns),
                *((str(value.value), value.confidence) for value in features.materials),
            ],
            [*profile.patterns, *profile.materials],
            features.quality.score,
        )
        if pattern_material is not None:
            components.append(pattern_material)
        shape_detail = self._categorical_component(
            MatchDimension.SHAPE_DETAIL,
            [
                *((str(value.value), value.confidence) for value in features.shape_traits),
                *((str(value.value), value.confidence) for value in features.decorative_details),
            ],
            [*profile.shape_traits, *profile.decorative_details],
            features.quality.score,
        )
        if shape_detail is not None:
            components.append(shape_detail)
        components.append(
            _Component(
                dimension=MatchDimension.SEMANTIC_EMBEDDING,
                score=max(0.0, min(1.0, self._cosine(embedding.values, profile.embedding_centroid.values))),
                confidence=features.quality.score,
                candidate_values=["candidate feature representation"],
                profile_values=["profile feature representation"],
                matching_values=["overall visual feature mix"],
                contrasting_values=[],
            )
        )
        return components

    def _colour_component(
        self,
        features: ItemVisualFeaturesV1,
        profile: AestheticProfileV1,
    ) -> _Component | None:
        candidate_colours = [
            (colour, colour.proportion * colour.confidence)
            for colour in features.colours
            if colour.proportion * colour.confidence > 0
        ]
        if not candidate_colours or not profile.colours:
            return None
        total_candidate_weight = sum(weight for _, weight in candidate_colours)
        max_profile_weight = max(colour.weight for colour in profile.colours)
        score = 0.0
        matching: list[str] = []
        contrasting: list[str] = []
        profile_values: list[str] = []
        for candidate, candidate_weight in candidate_colours:
            best_profile, similarity = max(
                (
                    (profile_colour, self._colour_similarity(candidate.hex, profile_colour.hex))
                    for profile_colour in profile.colours
                ),
                key=lambda pair: pair[1],
            )
            prominence = best_profile.weight / max_profile_weight
            score += (
                candidate_weight
                * similarity
                * (0.5 + 0.5 * prominence)
                / total_candidate_weight
            )
            profile_values.append(best_profile.name)
            if similarity >= 0.70:
                matching.append(candidate.name)
            elif similarity <= 0.35:
                contrasting.append(candidate.name)
        confidence = min(
            features.quality.score,
            sum(colour.confidence * weight for colour, weight in candidate_colours)
            / total_candidate_weight,
        )
        return _Component(
            dimension=MatchDimension.COLOUR,
            score=score,
            confidence=confidence,
            candidate_values=[colour.name for colour, _ in candidate_colours],
            profile_values=self._deduplicate(profile_values),
            matching_values=self._deduplicate(matching),
            contrasting_values=self._deduplicate(contrasting),
        )

    def _categorical_component(
        self,
        dimension: MatchDimension,
        candidates: list[tuple[str, float]],
        profile_features: list[WeightedFeature],
        quality_score: float,
    ) -> _Component | None:
        candidates = [(value, confidence) for value, confidence in candidates if confidence > 0]
        if not candidates or not profile_features:
            return None
        profile_weights = {feature.value: feature.weight for feature in profile_features}
        max_profile_weight = max(profile_weights.values())
        total_confidence = sum(confidence for _, confidence in candidates)
        score = sum(
            confidence
            * (
                0.5 + 0.5 * profile_weights[value] / max_profile_weight
                if value in profile_weights
                else 0.0
            )
            for value, confidence in candidates
        ) / total_confidence
        candidate_values = [value for value, _ in candidates]
        matching = [value for value in candidate_values if value in profile_weights]
        contrasting = [value for value in candidate_values if value not in profile_weights]
        confidence = min(
            quality_score,
            total_confidence / len(candidates),
        )
        return _Component(
            dimension=dimension,
            score=score,
            confidence=confidence,
            candidate_values=self._deduplicate(candidate_values),
            profile_values=[feature.value for feature in profile_features[:3]],
            matching_values=self._deduplicate(matching),
            contrasting_values=self._deduplicate(contrasting),
        )

    def _classify(
        self,
        *,
        overall_score: float,
        components: list[_Component],
        profile: AestheticProfileV1,
    ) -> MatchClassification:
        confident_components = [component for component in components if component.confidence >= 0.35]
        if len(confident_components) < 2:
            return MatchClassification.UNCERTAIN

        principal = [
            component
            for component in confident_components
            if component.dimension != MatchDimension.SEMANTIC_EMBEDDING
        ]
        strong = [
            component
            for component in principal
            if component.score >= self._config.intentional_match_threshold
        ]
        contrasts = [
            component
            for component in principal
            if component.score <= self._config.intentional_contrast_threshold
        ]
        if len(strong) >= 2 and len(contrasts) == 1 and self._supports_contrast(
            contrasts[0].dimension, profile
        ):
            return MatchClassification.INTENTIONAL_CONTRAST
        if overall_score >= self._config.strong_fit_threshold:
            return MatchClassification.STRONG_FIT
        if overall_score >= self._config.moderate_fit_threshold:
            return MatchClassification.MODERATE_FIT
        return MatchClassification.WEAK_FIT

    def _supports_contrast(
        self,
        dimension: MatchDimension,
        profile: AestheticProfileV1,
    ) -> bool:
        if dimension == MatchDimension.COLOUR:
            return profile.colour_diversity >= self._config.diversity_threshold
        if dimension == MatchDimension.STYLE:
            return profile.style_diversity >= self._config.diversity_threshold
        return max(profile.colour_diversity, profile.style_diversity) >= self._config.diversity_threshold

    def _evidence(
        self,
        components: list[_Component],
        classification: MatchClassification,
    ) -> tuple[list[MatchEvidence], list[MatchEvidence]]:
        matching: list[MatchEvidence] = []
        contrasting: list[MatchEvidence] = []
        ordered_components = sorted(
            components,
            key=lambda value: (
                value.dimension == MatchDimension.SEMANTIC_EMBEDDING,
                -value.score,
            ),
        )
        for component in ordered_components:
            if component.score >= 0.60 and component.matching_values:
                matching.append(self._make_evidence(component, contrast=False))
            if component.score <= 0.35 and component.contrasting_values:
                contrasting.append(self._make_evidence(component, contrast=True))
        if classification == MatchClassification.WEAK_FIT and not contrasting:
            principal_components = [
                component
                for component in components
                if component.dimension != MatchDimension.SEMANTIC_EMBEDDING
            ]
            if principal_components:
                weakest = min(principal_components, key=lambda value: value.score)
                contrasting.append(self._make_limited_evidence(weakest))
        return matching[:2], contrasting[:1]

    def _make_evidence(self, component: _Component, *, contrast: bool) -> MatchEvidence:
        candidate_values = (
            component.contrasting_values if contrast else component.matching_values
        )[:2]
        profile_values = component.profile_values[:2]
        candidate_text = self._natural_list(
            [self._display(value) for value in candidate_values]
        )
        if component.dimension == MatchDimension.SEMANTIC_EMBEDDING:
            statement = "Its overall visual character is similar to your profile."
        elif contrast:
            is_plural = len(candidate_values) > 1 and component.dimension != MatchDimension.COLOUR
            dimension_text = {
                MatchDimension.COLOUR: "palette",
                MatchDimension.STYLE: "style traits" if is_plural else "style trait",
                MatchDimension.PATTERN_MATERIAL: (
                    "patterns or materials" if is_plural else "pattern or material"
                ),
                MatchDimension.SHAPE_DETAIL: (
                    "shape or detail traits" if is_plural else "shape or detail trait"
                ),
            }[component.dimension]
            verb = "differ" if is_plural else "differs"
            statement = f"Its {candidate_text} {dimension_text} {verb} from your profile."
        else:
            is_plural = len(candidate_values) > 1 and component.dimension != MatchDimension.COLOUR
            dimension_text = {
                MatchDimension.COLOUR: "palette",
                MatchDimension.STYLE: "style traits" if is_plural else "style trait",
                MatchDimension.PATTERN_MATERIAL: (
                    "patterns or materials" if is_plural else "pattern or material"
                ),
                MatchDimension.SHAPE_DETAIL: (
                    "shape or detail traits" if is_plural else "shape or detail trait"
                ),
            }[component.dimension]
            verb = "appear" if is_plural else "appears"
            statement = f"Its {candidate_text} {dimension_text} also {verb} in your profile."
        return MatchEvidence(
            dimension=component.dimension,
            candidate_values=candidate_values,
            profile_values=profile_values,
            statement=statement,
            confidence=component.confidence,
        )

    def _make_limited_evidence(self, component: _Component) -> MatchEvidence:
        candidate_values = (component.contrasting_values or component.candidate_values)[:2]
        dimension_text, verb = {
            MatchDimension.COLOUR: ("palette", "has"),
            MatchDimension.STYLE: ("style traits", "have"),
            MatchDimension.PATTERN_MATERIAL: ("patterns and materials", "have"),
            MatchDimension.SHAPE_DETAIL: ("shape and detail traits", "have"),
        }[component.dimension]
        statement = f"Its {dimension_text} {verb} limited overlap with your profile."
        return MatchEvidence(
            dimension=component.dimension,
            candidate_values=candidate_values,
            profile_values=component.profile_values[:2],
            statement=statement,
            confidence=component.confidence,
        )

    def _explanation(
        self,
        classification: MatchClassification,
        matching: list[MatchEvidence],
        contrasting: list[MatchEvidence],
    ) -> str:
        labels = {
            MatchClassification.STRONG_FIT: "Strong Fit",
            MatchClassification.MODERATE_FIT: "Moderate Fit",
            MatchClassification.INTENTIONAL_CONTRAST: "Intentional Contrast",
            MatchClassification.WEAK_FIT: "Weak Fit",
            MatchClassification.UNCERTAIN: "Uncertain",
        }
        qualifier = "Based on your uploaded items, this is subjective guidance rather than a rule."
        if classification == MatchClassification.UNCERTAIN:
            matching_text = "There is not enough confident evidence to identify a reliable match."
            contrasting_text = "There is not enough confident evidence to identify a reliable contrast."
        else:
            matching_text = " ".join(
                evidence.statement for evidence in matching[:2]
            ) or "No strong matching evidence was identified."
            contrasting_text = " ".join(
                evidence.statement for evidence in contrasting[:1]
            ) or "No major contrasting feature was identified."
            if classification == MatchClassification.WEAK_FIT:
                contrasting_text = (
                    f"{contrasting_text} Overall, the similarities are limited "
                    "across the item as a whole."
                )

        return "\n\n".join(
            [
                f"Classification: {labels[classification]}",
                f"Matching Evidence: {matching_text}",
                f"Contrasting Evidence: {contrasting_text}",
                f"Subjective Qualifier: {qualifier}",
            ]
        )

    def _ensure_compatible_embeddings(
        self,
        candidate: SemanticEmbedding,
        profile: SemanticEmbedding,
    ) -> None:
        if (
            candidate.provider,
            candidate.model,
            candidate.dimensions,
            candidate.schema_version,
            candidate.input_type,
        ) != (
            profile.provider,
            profile.model,
            profile.dimensions,
            profile.schema_version,
            profile.input_type,
        ):
            raise MatchBuildError("Candidate and profile embeddings are incompatible")

    def _colour_similarity(self, left: str, right: str) -> float:
        left_rgb = self._hex_to_rgb(left)
        right_rgb = self._hex_to_rgb(right)
        distance = sqrt(sum((a - b) ** 2 for a, b in zip(left_rgb, right_rgb, strict=True)))
        return max(0.0, 1.0 - distance / sqrt(3 * 255**2))

    def _cosine(self, left: list[float], right: list[float]) -> float:
        left_magnitude = sqrt(sum(value * value for value in left))
        right_magnitude = sqrt(sum(value * value for value in right))
        if left_magnitude == 0 or right_magnitude == 0:
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True)) / (
            left_magnitude * right_magnitude
        )

    def _hex_to_rgb(self, value: str) -> tuple[int, int, int]:
        return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]

    def _deduplicate(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    def _display(self, value: str) -> str:
        return value.replace("_", " ")

    def _natural_list(self, values: list[str]) -> str:
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return f"{values[0]} and {values[1]}"
        return ", ".join(values[:-1]) + f", and {values[-1]}"
