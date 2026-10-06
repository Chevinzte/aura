from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import log, sqrt
from typing import Protocol
from uuid import UUID, uuid4

from aura_backend.domain.models import (
    AestheticProfileV1,
    ItemVisualFeaturesV1,
    SemanticEmbedding,
    WeightedColour,
    WeightedFeature,
)
from aura_backend.repositories.supabase import FeaturePipelineVersion


class ProfileBuildError(ValueError):
    """Raised when compatible owned-item evidence cannot form a profile."""


class ProfilePersistenceError(RuntimeError):
    """Raised when a profile snapshot cannot be loaded or persisted."""


@dataclass(frozen=True, slots=True)
class ProfileInput:
    feature_id: UUID
    content_sha256: str
    features: ItemVisualFeaturesV1
    embedding: SemanticEmbedding


@dataclass(frozen=True, slots=True)
class BuiltProfile:
    profile: AestheticProfileV1
    effective_weights: dict[UUID, float]


@dataclass(frozen=True, slots=True)
class ProfileRebuildResult:
    status: str
    profile_id: UUID | None = None
    profile: AestheticProfileV1 | None = None


class ProfileRepository(Protocol):
    def list_profile_inputs(
        self, *, user_id: UUID, pipeline: FeaturePipelineVersion
    ) -> list[ProfileInput]: ...

    def activate_profile(
        self,
        *,
        profile_id: UUID,
        profile: AestheticProfileV1,
        effective_weights: dict[UUID, float],
        pipeline: FeaturePipelineVersion,
    ) -> object: ...


class AestheticProfileBuilder:
    """Build deterministic profile version 1 from analyzed owned items."""

    minimum_items = 5

    def build(self, *, user_id: UUID, inputs: list[ProfileInput]) -> BuiltProfile:
        if len(inputs) < self.minimum_items:
            raise ProfileBuildError("At least five usable owned items are required")
        self._validate_embeddings(inputs)

        effective_weights = self._effective_item_weights(inputs)
        colours = self._aggregate_colours(inputs, effective_weights)
        distributions = {
            "patterns": self._aggregate_observations(inputs, effective_weights, "patterns"),
            "materials": self._aggregate_observations(inputs, effective_weights, "materials"),
            "textures": self._aggregate_observations(inputs, effective_weights, "textures"),
            "shape_traits": self._aggregate_observations(
                inputs, effective_weights, "shape_traits"
            ),
            "decorative_details": self._aggregate_observations(
                inputs, effective_weights, "decorative_details"
            ),
            "style_traits": self._aggregate_observations(
                inputs, effective_weights, "style_traits"
            ),
            "aesthetic_signals": self._aggregate_observations(
                inputs, effective_weights, "aesthetic_signals"
            ),
        }
        embedding_centroid = self._embedding_centroid(inputs, effective_weights)
        summary = self._summary(colours, distributions["style_traits"])

        profile = AestheticProfileV1(
            user_id=user_id,
            colours=colours,
            **distributions,
            embedding_centroid=embedding_centroid,
            colour_diversity=self._diversity([colour.weight for colour in colours]),
            style_diversity=self._diversity(
                [feature.weight for feature in distributions["style_traits"]]
            ),
            contributing_feature_ids=[item.feature_id for item in inputs],
            summary=summary,
            algorithm_version=1,
        )
        return BuiltProfile(profile=profile, effective_weights=effective_weights)

    def _validate_embeddings(self, inputs: list[ProfileInput]) -> None:
        first = inputs[0].embedding
        compatibility = (
            first.provider,
            first.model,
            first.dimensions,
            first.schema_version,
            first.input_type,
        )
        if any(
            (
                item.embedding.provider,
                item.embedding.model,
                item.embedding.dimensions,
                item.embedding.schema_version,
                item.embedding.input_type,
            )
            != compatibility
            for item in inputs[1:]
        ):
            raise ProfileBuildError("Profile inputs contain incompatible embeddings")

    def _effective_item_weights(self, inputs: list[ProfileInput]) -> dict[UUID, float]:
        parents = list(range(len(inputs)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        for left in range(len(inputs)):
            for right in range(left + 1, len(inputs)):
                if self._are_duplicates(inputs[left], inputs[right]):
                    union(left, right)

        group_sizes: dict[int, int] = defaultdict(int)
        for index in range(len(inputs)):
            group_sizes[find(index)] += 1

        raw_weights = [1.0 / group_sizes[find(index)] for index in range(len(inputs))]
        total = sum(raw_weights)
        return {
            item.feature_id: raw_weight / total
            for item, raw_weight in zip(inputs, raw_weights, strict=True)
        }

    def _are_duplicates(self, left: ProfileInput, right: ProfileInput) -> bool:
        if left.content_sha256 == right.content_sha256:
            return True
        if left.features.item_type.value != right.features.item_type.value:
            return False
        left_values = self._feature_signature(left.features)
        right_values = self._feature_signature(right.features)
        union = left_values | right_values
        feature_similarity = len(left_values & right_values) / len(union) if union else 1.0
        return feature_similarity >= 0.8 and self._cosine(
            left.embedding.values, right.embedding.values
        ) >= 0.985

    def _feature_signature(self, features: ItemVisualFeaturesV1) -> set[str]:
        signature = {f"colour:{colour.name.lower()}" for colour in features.colours}
        for field_name in (
            "patterns",
            "materials",
            "textures",
            "shape_traits",
            "decorative_details",
            "style_traits",
            "aesthetic_signals",
        ):
            signature.update(
                f"{field_name}:{observation.value}"
                for observation in getattr(features, field_name)
            )
        return signature

    def _aggregate_colours(
        self,
        inputs: list[ProfileInput],
        item_weights: dict[UUID, float],
    ) -> list[WeightedColour]:
        weights: dict[str, float] = defaultdict(float)
        rgb_sums: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
        for item in inputs:
            for colour in item.features.colours:
                contribution = (
                    item_weights[item.feature_id] * colour.proportion * colour.confidence
                )
                if contribution <= 0:
                    continue
                key = colour.name.strip().lower()
                weights[key] += contribution
                red, green, blue = self._hex_to_rgb(colour.hex)
                rgb_sums[key][0] += red * contribution
                rgb_sums[key][1] += green * contribution
                rgb_sums[key][2] += blue * contribution

        total = sum(weights.values())
        if total <= 0:
            raise ProfileBuildError("Profile inputs contain no confident colour evidence")
        return [
            WeightedColour(
                name=name,
                hex=self._rgb_to_hex(
                    *(component / weight for component in rgb_sums[name])
                ),
                weight=weight / total,
            )
            for name, weight in sorted(weights.items(), key=lambda pair: (-pair[1], pair[0]))
        ]

    def _aggregate_observations(
        self,
        inputs: list[ProfileInput],
        item_weights: dict[UUID, float],
        field_name: str,
    ) -> list[WeightedFeature]:
        weights: dict[str, float] = defaultdict(float)
        for item in inputs:
            for observation in getattr(item.features, field_name):
                weights[str(observation.value)] += (
                    item_weights[item.feature_id] * observation.confidence
                )
        total = sum(weights.values())
        if total <= 0:
            return []
        return [
            WeightedFeature(value=value, weight=weight / total)
            for value, weight in sorted(weights.items(), key=lambda pair: (-pair[1], pair[0]))
        ]

    def _embedding_centroid(
        self,
        inputs: list[ProfileInput],
        item_weights: dict[UUID, float],
    ) -> SemanticEmbedding:
        first = inputs[0].embedding
        values = [0.0] * first.dimensions
        for item in inputs:
            for index, value in enumerate(item.embedding.values):
                values[index] += value * item_weights[item.feature_id]
        magnitude = sqrt(sum(value * value for value in values))
        if magnitude == 0:
            raise ProfileBuildError("Embedding centroid cannot be a zero vector")
        return SemanticEmbedding(
            provider=first.provider,
            model=first.model,
            dimensions=first.dimensions,
            schema_version=first.schema_version,
            values=[value / magnitude for value in values],
        )

    def _summary(
        self,
        colours: list[WeightedColour],
        style_traits: list[WeightedFeature],
    ) -> str:
        colour_text = self._natural_list([colour.name for colour in colours[:3]])
        if style_traits:
            style_text = self._natural_list([trait.value.replace("_", " ") for trait in style_traits[:3]])
            return (
                f"Based on your uploaded belongings, your profile leans toward "
                f"{colour_text}, with {style_text} style traits."
            )
        return f"Based on your uploaded belongings, your profile leans toward {colour_text}."

    def _diversity(self, weights: list[float]) -> float:
        if len(weights) <= 1:
            return 0.0
        entropy = -sum(weight * log(weight) for weight in weights if weight > 0)
        return min(1.0, max(0.0, entropy / log(len(weights))))

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

    def _rgb_to_hex(self, red: float, green: float, blue: float) -> str:
        return f"#{round(red):02X}{round(green):02X}{round(blue):02X}"

    def _natural_list(self, values: list[str]) -> str:
        if len(values) == 1:
            return values[0]
        return ", ".join(values[:-1]) + f", and {values[-1]}"


class ProfileService:
    """Load compatible profile inputs and activate a new immutable snapshot."""

    def __init__(
        self,
        *,
        repository: ProfileRepository,
        builder: AestheticProfileBuilder,
        pipeline: FeaturePipelineVersion,
    ) -> None:
        self._repository = repository
        self._builder = builder
        self._pipeline = pipeline

    def rebuild_if_ready(self, user_id: UUID) -> ProfileRebuildResult:
        try:
            inputs = self._repository.list_profile_inputs(
                user_id=user_id,
                pipeline=self._pipeline,
            )
        except Exception as error:
            raise ProfilePersistenceError("Could not load profile inputs") from error
        if len(inputs) < self._builder.minimum_items:
            return ProfileRebuildResult(status="COLLECTING")

        built = self._builder.build(user_id=user_id, inputs=inputs)
        profile_id = uuid4()
        try:
            self._repository.activate_profile(
                profile_id=profile_id,
                profile=built.profile,
                effective_weights=built.effective_weights,
                pipeline=self._pipeline,
            )
        except Exception as error:
            raise ProfilePersistenceError("Could not activate aesthetic profile") from error
        return ProfileRebuildResult(
            status="READY",
            profile_id=profile_id,
            profile=built.profile,
        )
