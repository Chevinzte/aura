from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
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
    from aura_backend.application.preferences import FashionPresentation
    from aura_backend.application.profile_management import ProfileItemSummary
    from aura_backend.application.profiles import ProfileInput
    from aura_backend.application.suggestions import SuggestionCategory, SuggestionIntent
    from aura_backend.application.wardrobe import (
        CorrectionField,
        WardrobeItemRecord,
        WardrobeItemSummary,
    )


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

    def update_user_fashion_presentation(
        self,
        *,
        user_id: UUID,
        fashion_presentation: FashionPresentation,
    ) -> dict[str, Any]:
        response = (
            self._client.table("users")
            .update({"fashion_presentation": fashion_presentation.value})
            .eq("id", str(user_id))
            .execute()
        )
        return _require_single_row(response.data, "updating fashion presentation")

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
                "items!inner(id,content_sha256)"
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

        correction_rows = self._list_active_correction_rows(user_id=user_id)
        corrections = {
            str(row["source_features_id"]): row
            for row in correction_rows
            if isinstance(row, dict)
            and row.get("source_features_id")
            and row.get("embedding_provider") == pipeline.embedding_provider
            and row.get("embedding_model") == pipeline.embedding_model
            and row.get("embedding_dimensions") == pipeline.embedding_dimensions
            and row.get("embedding_schema_version") == pipeline.embedding_schema_version
            and row.get("feature_schema_version") == pipeline.feature_schema_version
        }
        inputs: list[ProfileInput] = []
        for row in response.data:
            if not isinstance(row, dict) or not isinstance(row.get("items"), dict):
                raise RepositoryError("Malformed profile input row")
            correction = corrections.get(str(row["id"]))
            effective = correction if correction is not None else row
            embedding_values = _parse_vector(effective.get("embedding"))
            inputs.append(
                ProfileInput(
                    feature_id=UUID(str(row["id"])),
                    content_sha256=str(row["items"]["content_sha256"]),
                    features=ItemVisualFeaturesV1.model_validate(
                        effective.get("corrected_features", effective.get("features"))
                    ),
                    embedding=SemanticEmbedding(
                        provider=str(effective["embedding_provider"]),
                        model=str(effective["embedding_model"]),
                        dimensions=int(effective["embedding_dimensions"]),
                        schema_version=int(effective["embedding_schema_version"]),
                        values=embedding_values,
                    ),
                    correction_id=(
                        UUID(str(correction["id"])) if correction is not None else None
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
        correction_ids: dict[UUID, UUID | None] | None = None,
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
                            "correction_id": (
                                str(correction_ids[feature_id])
                                if correction_ids and correction_ids.get(feature_id)
                                else None
                            ),
                        }
                        for feature_id, weight in effective_weights.items()
                    ],
                },
            )
            .execute()
        )
        return _require_single_row(response.data, "activating aesthetic profile")

    def list_owned_wardrobe_items(
        self,
        *,
        user_id: UUID,
        pipeline: FeaturePipelineVersion,
        limit: int,
        offset: int = 0,
    ) -> list[WardrobeItemSummary]:
        from aura_backend.application.wardrobe import WardrobeItemSummary

        response = (
            self._client.table("items")
            .select("id,item_name,created_at,item_visual_features!inner(id,features)")
            .eq("user_id", str(user_id))
            .eq("source", ItemSource.OWNED.value)
            .eq("status", "READY")
            .is_("deleted_at", "null")
            .eq("item_visual_features.status", "COMPLETED")
            .eq("item_visual_features.vision_provider", pipeline.vision_provider)
            .eq("item_visual_features.vision_model", pipeline.vision_model)
            .eq(
                "item_visual_features.vision_prompt_version",
                str(pipeline.vision_prompt_version),
            )
            .eq(
                "item_visual_features.feature_schema_version",
                str(pipeline.feature_schema_version),
            )
            .eq("item_visual_features.embedding_provider", pipeline.embedding_provider)
            .eq("item_visual_features.embedding_model", pipeline.embedding_model)
            .eq(
                "item_visual_features.embedding_dimensions",
                str(pipeline.embedding_dimensions),
            )
            .eq(
                "item_visual_features.embedding_schema_version",
                str(pipeline.embedding_schema_version),
            )
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        if not isinstance(response.data, list):
            raise RepositoryError("Expected rows while listing wardrobe items")
        corrections = {
            str(row["item_id"]): row
            for row in self._list_active_correction_rows(user_id=user_id)
            if isinstance(row, dict) and row.get("item_id")
        }
        items: list[WardrobeItemSummary] = []
        for row in response.data:
            feature_rows = row.get("item_visual_features") if isinstance(row, dict) else None
            if not isinstance(feature_rows, list) or not feature_rows:
                raise RepositoryError("Wardrobe item is missing visual features")
            source = feature_rows[0]
            correction = corrections.get(str(row["id"]))
            if correction is not None and not self._correction_matches_pipeline(
                correction=correction,
                source_features_id=source.get("id"),
                pipeline=pipeline,
            ):
                correction = None
            features = (
                correction.get("corrected_features")
                if correction is not None
                else source.get("features")
            )
            validated = ItemVisualFeaturesV1.model_validate(features)
            label = (
                validated.item_name
                if correction is not None
                else row.get("item_name") or validated.item_name or validated.item_type.value
            )
            items.append(
                WardrobeItemSummary(
                    item_id=UUID(str(row["id"])),
                    label=str(label).strip()[:80] or "Belonging",
                    created_at=_require_datetime(row.get("created_at")),
                )
            )
        return items

    def get_owned_wardrobe_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        pipeline: FeaturePipelineVersion,
    ) -> WardrobeItemRecord | None:
        from aura_backend.application.wardrobe import CorrectionField, WardrobeItemRecord

        response = (
            self._client.table("items")
            .select(
                "id,user_id,created_at,storage_path,mime_type,"
                "item_visual_features!inner(id,features)"
            )
            .eq("id", str(item_id))
            .eq("user_id", str(user_id))
            .eq("source", ItemSource.OWNED.value)
            .eq("status", "READY")
            .is_("deleted_at", "null")
            .eq("item_visual_features.status", "COMPLETED")
            .eq("item_visual_features.vision_provider", pipeline.vision_provider)
            .eq("item_visual_features.vision_model", pipeline.vision_model)
            .eq(
                "item_visual_features.vision_prompt_version",
                str(pipeline.vision_prompt_version),
            )
            .eq(
                "item_visual_features.feature_schema_version",
                str(pipeline.feature_schema_version),
            )
            .eq("item_visual_features.embedding_provider", pipeline.embedding_provider)
            .eq("item_visual_features.embedding_model", pipeline.embedding_model)
            .eq(
                "item_visual_features.embedding_dimensions",
                str(pipeline.embedding_dimensions),
            )
            .eq(
                "item_visual_features.embedding_schema_version",
                str(pipeline.embedding_schema_version),
            )
            .execute()
        )
        row = _optional_single_row(response.data, "loading wardrobe item")
        if row is None:
            return None
        feature_rows = row.get("item_visual_features")
        if not isinstance(feature_rows, list) or not feature_rows:
            raise RepositoryError("Wardrobe item is missing visual features")
        source = feature_rows[0]
        corrections = [
            correction
            for correction in self._list_active_correction_rows(user_id=user_id)
            if str(correction.get("item_id")) == str(item_id)
        ]
        correction = corrections[0] if corrections else None
        if correction is not None and not self._correction_matches_pipeline(
            correction=correction,
            source_features_id=source.get("id"),
            pipeline=pipeline,
        ):
            correction = None
        features = (
            correction.get("corrected_features")
            if correction is not None
            else source.get("features")
        )
        fields = correction.get("corrected_fields", []) if correction is not None else []
        revision_kind = (
            str(correction.get("revision_kind")) if correction is not None else None
        )
        if revision_kind == "AI_REANALYSIS":
            fields = []
        return WardrobeItemRecord(
            item_id=UUID(str(row["id"])),
            user_id=UUID(str(row["user_id"])),
            source_features_id=UUID(str(source["id"])),
            storage_path=str(row["storage_path"]),
            mime_type=str(row["mime_type"]),
            created_at=_require_datetime(row.get("created_at")),
            features=ItemVisualFeaturesV1.model_validate(features),
            corrected_fields=[CorrectionField(value) for value in fields],
            active_correction_id=(
                UUID(str(correction["id"])) if correction is not None else None
            ),
            revision_kind=revision_kind,
        )

    def activate_item_feature_correction(
        self,
        *,
        correction_id: UUID,
        user_id: UUID,
        item_id: UUID,
        source_features_id: UUID,
        corrected_features: ItemVisualFeaturesV1,
        canonical_embedding_text: str,
        embedding: SemanticEmbedding,
        corrected_fields: list[CorrectionField],
        pipeline: FeaturePipelineVersion,
    ) -> dict[str, Any]:
        response = self._client.rpc(
            "activate_item_feature_correction",
            {
                "p_correction_id": str(correction_id),
                "p_user_id": str(user_id),
                "p_item_id": str(item_id),
                "p_source_features_id": str(source_features_id),
                "p_corrected_features": corrected_features.model_dump(
                    by_alias=True, mode="json"
                ),
                "p_canonical_embedding_text": canonical_embedding_text,
                "p_embedding": embedding.values,
                "p_corrected_fields": [field.value for field in corrected_fields],
                "p_embedding_provider": embedding.provider,
                "p_embedding_model": embedding.model,
                "p_embedding_dimensions": embedding.dimensions,
                "p_embedding_schema_version": embedding.schema_version,
                "p_feature_schema_version": pipeline.feature_schema_version,
            },
        ).execute()
        return _require_single_row(response.data, "activating item feature correction")

    def restore_item_feature_correction(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        correction_id: UUID,
        previous_correction_id: UUID | None,
    ) -> None:
        self._client.rpc(
            "restore_item_feature_correction",
            {
                "p_user_id": str(user_id),
                "p_item_id": str(item_id),
                "p_failed_correction_id": str(correction_id),
                "p_previous_correction_id": (
                    str(previous_correction_id) if previous_correction_id else None
                ),
            },
        ).execute()

    def create_item_reanalysis_preview(
        self,
        *,
        revision_id: UUID,
        user_id: UUID,
        item_id: UUID,
        source_features_id: UUID,
        features: ItemVisualFeaturesV1,
        canonical_embedding_text: str,
        embedding: SemanticEmbedding,
        corrected_fields: list[Any],
        pipeline: FeaturePipelineVersion,
    ) -> dict[str, Any]:
        response = self._client.rpc(
            "create_item_reanalysis_preview",
            {
                "p_revision_id": str(revision_id),
                "p_user_id": str(user_id),
                "p_item_id": str(item_id),
                "p_source_features_id": str(source_features_id),
                "p_features": features.model_dump(by_alias=True, mode="json"),
                "p_canonical_embedding_text": canonical_embedding_text,
                "p_embedding": embedding.values,
                "p_corrected_fields": [field.value for field in corrected_fields],
                "p_embedding_provider": embedding.provider,
                "p_embedding_model": embedding.model,
                "p_embedding_dimensions": embedding.dimensions,
                "p_embedding_schema_version": embedding.schema_version,
                "p_feature_schema_version": pipeline.feature_schema_version,
            },
        ).execute()
        return _require_single_row(response.data, "creating reanalysis preview")

    def activate_item_reanalysis(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        revision_id: UUID,
    ) -> dict[str, Any]:
        response = self._client.rpc(
            "activate_item_reanalysis",
            {
                "p_user_id": str(user_id),
                "p_item_id": str(item_id),
                "p_revision_id": str(revision_id),
            },
        ).execute()
        return _require_single_row(response.data, "activating reanalysis")

    def discard_item_reanalysis(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        revision_id: UUID,
    ) -> None:
        self._client.rpc(
            "discard_item_reanalysis",
            {
                "p_user_id": str(user_id),
                "p_item_id": str(item_id),
                "p_revision_id": str(revision_id),
            },
        ).execute()

    def _list_active_correction_rows(self, *, user_id: UUID) -> list[dict[str, Any]]:
        response = (
            self._client.table("item_feature_corrections")
            .select(
                "id,item_id,source_features_id,corrected_features,corrected_fields,"
                "embedding,embedding_provider,embedding_model,embedding_dimensions,"
                "embedding_schema_version,feature_schema_version,revision_kind"
            )
            .eq("user_id", str(user_id))
            .eq("is_active", "true")
            .execute()
        )
        if not isinstance(response.data, list) or not all(
            isinstance(row, dict) for row in response.data
        ):
            raise RepositoryError("Expected rows while loading active corrections")
        return response.data

    @staticmethod
    def _correction_matches_pipeline(
        *,
        correction: dict[str, Any],
        source_features_id: Any,
        pipeline: FeaturePipelineVersion,
    ) -> bool:
        return (
            str(correction.get("source_features_id")) == str(source_features_id)
            and correction.get("embedding_provider") == pipeline.embedding_provider
            and correction.get("embedding_model") == pipeline.embedding_model
            and correction.get("embedding_dimensions") == pipeline.embedding_dimensions
            and correction.get("embedding_schema_version")
            == pipeline.embedding_schema_version
            and correction.get("feature_schema_version")
            == pipeline.feature_schema_version
        )

    def get_active_profile(
        self,
        *,
        user_id: UUID,
        pipeline: FeaturePipelineVersion,
    ) -> Any:
        from aura_backend.application.matching import ActiveProfile

        response = (
            self._client.table("aesthetic_profiles")
            .select("id,profile_data,created_at")
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
            created_at=_parse_datetime(row.get("created_at")),
        )

    def list_owned_profile_items(
        self,
        *,
        user_id: UUID,
        pipeline: FeaturePipelineVersion,
        limit: int,
        offset: int = 0,
    ) -> list[ProfileItemSummary]:
        from aura_backend.application.profile_management import ProfileItemSummary

        response = (
            self._client.table("items")
            .select("id,item_name,created_at,item_visual_features!inner(features)")
            .eq("user_id", str(user_id))
            .eq("source", ItemSource.OWNED.value)
            .eq("status", "READY")
            .is_("deleted_at", "null")
            .eq("item_visual_features.status", "COMPLETED")
            .eq("item_visual_features.vision_provider", pipeline.vision_provider)
            .eq("item_visual_features.vision_model", pipeline.vision_model)
            .eq(
                "item_visual_features.vision_prompt_version",
                str(pipeline.vision_prompt_version),
            )
            .eq(
                "item_visual_features.feature_schema_version",
                str(pipeline.feature_schema_version),
            )
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        if not isinstance(response.data, list):
            raise RepositoryError("Expected rows while listing owned items")

        items: list[ProfileItemSummary] = []
        for row in response.data:
            if not isinstance(row, dict):
                raise RepositoryError("Malformed owned item row")
            feature_rows = row.get("item_visual_features")
            if not isinstance(feature_rows, list) or not feature_rows:
                raise RepositoryError("Owned item is missing visual features")
            features = feature_rows[0].get("features")
            if not isinstance(features, dict):
                raise RepositoryError("Owned item has malformed visual features")
            item_type = features.get("itemType")
            type_value = item_type.get("value") if isinstance(item_type, dict) else None
            label = row.get("item_name") or features.get("itemName") or type_value or "Belonging"
            items.append(
                ProfileItemSummary(
                    item_id=UUID(str(row["id"])),
                    label=str(label).strip()[:80] or "Belonging",
                    created_at=_require_datetime(row.get("created_at")),
                )
            )
        return items

    def remove_owned_item(self, *, user_id: UUID, item_id: UUID) -> None:
        response = self._client.rpc(
            "remove_owned_profile_item",
            {"p_user_id": str(user_id), "p_item_id": str(item_id)},
        ).execute()
        _require_single_row(response.data, "removing owned profile item")

    def reset_owned_items(self, *, user_id: UUID) -> int:
        response = self._client.rpc(
            "reset_owned_profile_items",
            {"p_user_id": str(user_id)},
        ).execute()
        if not isinstance(response.data, list):
            raise RepositoryError("Expected rows while resetting owned profile items")
        if not all(isinstance(row, dict) for row in response.data):
            raise RepositoryError("Malformed rows while resetting owned profile items")
        return len(response.data)

    def list_recent_suggestion_labels(
        self,
        *,
        user_id: UUID,
        limit: int,
    ) -> list[str]:
        response = (
            self._client.table("suggestion_history")
            .select("label")
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        if not isinstance(response.data, list):
            raise RepositoryError("Expected rows while loading suggestion history")
        labels: list[str] = []
        for row in response.data:
            if not isinstance(row, dict) or not isinstance(row.get("label"), str):
                raise RepositoryError("Malformed suggestion history row")
            labels.append(row["label"])
        return labels

    def record_suggestion_history(
        self,
        *,
        user_id: UUID,
        intent: SuggestionIntent,
        category: SuggestionCategory,
        concepts: list[tuple[str, str]],
    ) -> None:
        if not concepts:
            return
        response = (
            self._client.table("suggestion_history")
            .insert(
                [
                    {
                        "user_id": str(user_id),
                        "intent": intent.value,
                        "category": category.value,
                        "label": label,
                        "item_type": item_type,
                    }
                    for label, item_type in concepts
                ]
            )
            .execute()
        )
        if not isinstance(response.data, list) or len(response.data) != len(concepts):
            raise RepositoryError("Expected rows while recording suggestion history")

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


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise RepositoryError("Malformed timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RepositoryError("Malformed timestamp") from error


def _require_datetime(value: Any) -> datetime:
    parsed = _parse_datetime(value)
    if parsed is None:
        raise RepositoryError("Missing timestamp")
    return parsed
