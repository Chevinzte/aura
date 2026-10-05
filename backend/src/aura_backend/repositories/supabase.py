from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from supabase import Client

from aura_backend.domain.models import (
    ItemSource,
    ItemVisualFeaturesV1,
    SemanticEmbedding,
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
        response = (
            self._client.table("users")
            .upsert(
                {
                    "telegram_user_id": telegram_user_id,
                    "display_name": display_name,
                },
                on_conflict="telegram_user_id",
            )
            .execute()
        )
        return _require_single_row(response.data, "upserting user")

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


def _require_single_row(rows: Any, operation: str) -> dict[str, Any]:
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RepositoryError(f"Expected one row while {operation}")
    return rows[0]
