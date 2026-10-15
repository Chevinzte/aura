from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from supabase import Client

from aura_backend.domain.models import (
    AestheticProfileV1,
    FeedbackCategory,
    FeedbackType,
    ItemSource,
    ItemVisualFeaturesV1,
    MatchResultV1,
    SemanticEmbedding,
)

if TYPE_CHECKING:
    from aura_backend.application.profiles import ProfileInput


class RepositoryError(RuntimeError):
    """Raised when Supabase returns an unexpected persistence response."""


@dataclass(frozen=True, slots=True)
class FeaturePipelineVersion:
    """Identifies the versioned AI pipeline that produced an analysis record."""

    vision_provider: str
    vision_model: str
    vision_prompt_version: int
    feature_schema_version: int
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    embedding_schema_version: int


class AuraRepository:
    """Supabase persistence operations used by AURA application services."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def find_or_create_user(
        self,
        telegram_user_id: int,
        display_name: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"telegram_user_id": telegram_user_id}
        if display_name is not None:
            payload["display_name"] = display_name
        response = (
            self._client.table("users")
            .upsert(
                payload,
                on_conflict="telegram_user_id",
            )
            .execute()
        )
        return _require_single_row(response.data, "upserting user")

    def find_user_by_telegram_id(self, telegram_user_id: int) -> dict[str, Any] | None:
        response = (
            self._client.table("users")
            .select("id")
            .eq("telegram_user_id", str(telegram_user_id))
            .execute()
        )
        return _optional_single_row(response.data, "loading user")

    def create_item_with_analysis(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        source: ItemSource,
        storage_path: str,
        original_filename: str | None,
        mime_type: str,
        size_bytes: int,
        width_px: int,
        height_px: int,
        content_sha256: str,
        item_name: str | None,
        pipeline: FeaturePipelineVersion,
    ) -> dict[str, Any]:
        response = (
            self._client.rpc(
                "create_item_with_analysis",
                {
                    "p_item_id": str(item_id),
                    "p_user_id": str(user_id),
                    "p_source": source.value,
                    "p_storage_path": storage_path,
                    "p_original_filename": original_filename,
                    "p_mime_type": mime_type,
                    "p_size_bytes": size_bytes,
                    "p_width_px": width_px,
                    "p_height_px": height_px,
                    "p_content_sha256": content_sha256,
                    "p_item_name": item_name,
                    "p_vision_provider": pipeline.vision_provider,
                    "p_vision_model": pipeline.vision_model,
                    "p_vision_prompt_version": pipeline.vision_prompt_version,
                    "p_feature_schema_version": pipeline.feature_schema_version,
                    "p_embedding_provider": pipeline.embedding_provider,
                    "p_embedding_model": pipeline.embedding_model,
                    "p_embedding_dimensions": pipeline.embedding_dimensions,
                    "p_embedding_schema_version": pipeline.embedding_schema_version,
                },
            )
            .execute()
        )
        return _require_single_row(response.data, "creating item and feature analysis")

    def create_item(
        self,
        *,
        user_id: UUID,
        source: ItemSource,
        storage_path: str,
        original_filename: str | None,
        mime_type: str,
        size_bytes: int,
        content_sha256: str,
        width_px: int | None = None,
        height_px: int | None = None,
        item_name: str | None = None,
    ) -> dict[str, Any]:
        response = (
            self._client.table("items")
            .insert(
                {
                    "user_id": str(user_id),
                    "source": source.value,
                    "storage_path": storage_path,
                    "original_filename": original_filename,
                    "mime_type": mime_type,
                    "size_bytes": size_bytes,
                    "width_px": width_px,
                    "height_px": height_px,
                    "content_sha256": content_sha256,
                    "item_name": item_name,
                }
            )
            .execute()
        )
        return _require_single_row(response.data, "creating item")

    def create_pending_feature_analysis(
        self,
        *,
        item_id: UUID,
        pipeline: FeaturePipelineVersion,
    ) -> dict[str, Any]:
        response = (
            self._client.table("item_visual_features")
            .insert(
                {
                    "item_id": str(item_id),
                    "status": "PENDING",
                    "vision_provider": pipeline.vision_provider,
                    "vision_model": pipeline.vision_model,
                    "vision_prompt_version": pipeline.vision_prompt_version,
                    "feature_schema_version": pipeline.feature_schema_version,
                    "embedding_provider": pipeline.embedding_provider,
                    "embedding_model": pipeline.embedding_model,
                    "embedding_dimensions": pipeline.embedding_dimensions,
                    "embedding_schema_version": pipeline.embedding_schema_version,
                }
            )
            .execute()
        )
        return _require_single_row(response.data, "creating pending feature analysis")

    def mark_feature_analysis_processing(self, analysis_id: UUID) -> dict[str, Any]:
        response = (
            self._client.rpc(
                "start_item_feature_analysis",
                {"p_analysis_id": str(analysis_id)},
            )
            .execute()
        )
        return _require_single_row(response.data, "marking feature analysis processing")

    def complete_feature_analysis(
        self,
        *,
        analysis_id: UUID,
        features: ItemVisualFeaturesV1,
        canonical_embedding_text: str,
        embedding: SemanticEmbedding,
    ) -> dict[str, Any]:
        response = (
            self._client.rpc(
                "complete_item_feature_analysis",
                {
                    "p_analysis_id": str(analysis_id),
                    "p_features": features.model_dump(by_alias=True, mode="json"),
                    "p_canonical_embedding_text": canonical_embedding_text,
                    "p_embedding": embedding.values,
                },
            )
            .execute()
        )
        return _require_single_row(response.data, "completing feature analysis")

    def fail_feature_analysis(
        self,
        *,
        analysis_id: UUID,
        error_code: str,
        error_detail: str | None = None,
    ) -> dict[str, Any]:
        response = (
            self._client.rpc(
                "fail_item_feature_analysis",
                {
                    "p_analysis_id": str(analysis_id),
                    "p_error_code": error_code,
                    "p_error_detail": error_detail,
                },
            )
            .execute()
        )
        return _require_single_row(response.data, "failing feature analysis")

    def list_profile_inputs(
        self,
        *,
        user_id: UUID,
        pipeline: FeaturePipelineVersion,
    ) -> list[ProfileInput]:
        from aura_backend.application.profiles import ProfileInput

        response = (
            self._client.table("item_visual_features")
            .select(
                "id,features,embedding,embedding_provider,embedding_model,"
                "embedding_dimensions,embedding_schema_version,"
                "items!inner(content_sha256)"
            )
            .eq("status", "COMPLETED")
            .eq("vision_provider", pipeline.vision_provider)
            .eq("vision_model", pipeline.vision_model)
            .eq("vision_prompt_version", pipeline.vision_prompt_version)
            .eq("feature_schema_version", pipeline.feature_schema_version)
            .eq("embedding_provider", pipeline.embedding_provider)
            .eq("embedding_model", pipeline.embedding_model)
            .eq("embedding_dimensions", pipeline.embedding_dimensions)
            .eq("embedding_schema_version", pipeline.embedding_schema_version)
            .eq("items.user_id", str(user_id))
            .eq("items.source", ItemSource.OWNED.value)
            .eq("items.status", "READY")
            .is_("items.deleted_at", "null")
            .order("created_at")
            .execute()
        )
        if not isinstance(response.data, list):
            raise RepositoryError("Expected rows while loading profile inputs")

        inputs: list[ProfileInput] = []
        for row in response.data:
            if not isinstance(row, dict) or not isinstance(row.get("items"), dict):
                raise RepositoryError("Malformed profile input row")
            embedding_values = _parse_vector(row.get("embedding"))
            inputs.append(
                ProfileInput(
                    feature_id=UUID(str(row["id"])),
                    content_sha256=str(row["items"]["content_sha256"]),
                    features=ItemVisualFeaturesV1.model_validate(row["features"]),
                    embedding=SemanticEmbedding(
                        provider=str(row["embedding_provider"]),
                        model=str(row["embedding_model"]),
                        dimensions=int(row["embedding_dimensions"]),
                        schema_version=int(row["embedding_schema_version"]),
                        values=embedding_values,
                    ),
                )
            )
        return inputs

    def activate_profile(
        self,
        *,
        profile_id: UUID,
        profile: AestheticProfileV1,
        effective_weights: dict[UUID, float],
        pipeline: FeaturePipelineVersion,
    ) -> dict[str, Any]:
        response = (
            self._client.rpc(
                "activate_aesthetic_profile",
                {
                    "p_profile_id": str(profile_id),
                    "p_user_id": str(profile.user_id),
                    "p_profile_data": profile.model_dump(by_alias=True, mode="json"),
                    "p_embedding_centroid": profile.embedding_centroid.values,
                    "p_colour_diversity": profile.colour_diversity,
                    "p_style_diversity": profile.style_diversity,
                    "p_generated_summary": profile.summary,
                    "p_profile_algorithm_version": profile.algorithm_version,
                    "p_feature_schema_version": pipeline.feature_schema_version,
                    "p_embedding_model": pipeline.embedding_model,
                    "p_embedding_dimensions": pipeline.embedding_dimensions,
                    "p_embedding_schema_version": pipeline.embedding_schema_version,
                    "p_contributions": [
                        {
                            "feature_id": str(feature_id),
                            "effective_weight": weight,
                        }
                        for feature_id, weight in effective_weights.items()
                    ],
                },
            )
            .execute()
        )
        return _require_single_row(response.data, "activating aesthetic profile")

    def get_active_profile(
        self,
        *,
        user_id: UUID,
        pipeline: FeaturePipelineVersion,
    ) -> Any:
        from aura_backend.application.matching import ActiveProfile

        response = (
            self._client.table("aesthetic_profiles")
            .select("id,profile_data")
            .eq("user_id", str(user_id))
            .eq("is_active", "true")
            .eq("profile_algorithm_version", 1)
            .eq("feature_schema_version", pipeline.feature_schema_version)
            .eq("embedding_model", pipeline.embedding_model)
            .eq("embedding_dimensions", pipeline.embedding_dimensions)
            .eq("embedding_schema_version", pipeline.embedding_schema_version)
            .execute()
        )
        if not isinstance(response.data, list):
            raise RepositoryError("Expected rows while loading active profile")
        if not response.data:
            return None
        if len(response.data) != 1 or not isinstance(response.data[0], dict):
            raise RepositoryError("Expected one active aesthetic profile")
        row = response.data[0]
        return ActiveProfile(
            profile_id=UUID(str(row["id"])),
            profile=AestheticProfileV1.model_validate(row["profile_data"]),
        )

    def save_match_analysis(
        self,
        *,
        match_id: UUID,
        user_id: UUID,
        candidate_features_id: UUID,
        match: MatchResultV1,
    ) -> dict[str, Any]:
        response = (
            self._client.rpc(
                "record_completed_match",
                {
                    "p_match_id": str(match_id),
                    "p_user_id": str(user_id),
                    "p_candidate_item_id": str(match.candidate_item_id),
                    "p_candidate_features_id": str(candidate_features_id),
                    "p_profile_id": str(match.profile_id),
                    "p_overall_score": match.overall_score,
                    "p_classification": match.classification.value,
                    "p_component_scores": [
                        score.model_dump(by_alias=True, mode="json")
                        for score in match.component_scores
                    ],
                    "p_matching_evidence": [
                        evidence.model_dump(by_alias=True, mode="json")
                        for evidence in match.matching_evidence
                    ],
                    "p_contrasting_evidence": [
                        evidence.model_dump(by_alias=True, mode="json")
                        for evidence in match.contrasting_evidence
                    ],
                    "p_explanation": match.explanation,
                    "p_scoring_version": match.scoring_version,
                    "p_explanation_version": match.explanation_version,
                },
            )
            .execute()
        )
        return _require_single_row(response.data, "recording completed match")

    def match_belongs_to_user(self, *, match_id: UUID, user_id: UUID) -> bool:
        response = (
            self._client.table("match_analyses")
            .select("id")
            .eq("id", str(match_id))
            .eq("user_id", str(user_id))
            .eq("status", "COMPLETED")
            .execute()
        )
        return _optional_single_row(response.data, "checking match ownership") is not None

    def upsert_feedback(
        self,
        *,
        user_id: UUID,
        match_id: UUID,
        category: FeedbackCategory,
        feedback_type: FeedbackType,
        note: str | None,
    ) -> dict[str, Any]:
        response = (
            self._client.rpc(
                "upsert_match_feedback",
                {
                    "p_user_id": str(user_id),
                    "p_match_analysis_id": str(match_id),
                    "p_category": category.value,
                    "p_feedback_type": feedback_type.value,
                    "p_note": note,
                },
            )
            .execute()
        )
        return _require_single_row(response.data, "upserting match feedback")


def _require_single_row(rows: Any, operation: str) -> dict[str, Any]:
    if isinstance(rows, dict):
        return rows
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RepositoryError(f"Expected one row while {operation}")
    return rows[0]


def _optional_single_row(rows: Any, operation: str) -> dict[str, Any] | None:
    if not isinstance(rows, list) or len(rows) > 1:
        raise RepositoryError(f"Expected at most one row while {operation}")
    if not rows:
        return None
    if not isinstance(rows[0], dict):
        raise RepositoryError(f"Expected a row object while {operation}")
    return rows[0]


def _parse_vector(value: Any) -> list[float]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise RepositoryError("Malformed embedding vector") from error
    if not isinstance(value, list) or not all(
        isinstance(component, int | float) for component in value
    ):
        raise RepositoryError("Malformed embedding vector")
    return [float(component) for component in value]
