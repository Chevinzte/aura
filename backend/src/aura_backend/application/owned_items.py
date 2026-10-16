from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from aura_backend.ai.contracts import ImageInput
from aura_backend.application.item_analysis import ItemAnalysisResult, ItemAnalysisService
from aura_backend.application.profiles import (
    ProfileBuildError,
    ProfilePersistenceError,
    ProfileService,
)
from aura_backend.domain.models import ItemSource
from aura_backend.media.images import ImageValidator
from aura_backend.media.storage import ImageStorage
from aura_backend.repositories.supabase import FeaturePipelineVersion


class OwnedItemRepository(Protocol):
    def find_or_create_user(
        self, telegram_user_id: int, display_name: str | None
    ) -> dict[str, Any]: ...

    def create_item_with_analysis(self, **kwargs: Any) -> dict[str, Any]: ...


class OwnedItemError(RuntimeError):
    """Base error for owned-item ingestion."""


class OwnedItemStorageError(OwnedItemError):
    """Raised when the original image cannot be stored."""


class OwnedItemPersistenceError(OwnedItemError):
    """Raised when item metadata cannot be persisted atomically."""


@dataclass(frozen=True, slots=True)
class OwnedItemResult:
    item_id: UUID
    analysis: ItemAnalysisResult
    profile_status: str
    usable_item_count: int | None = None
    profile_id: UUID | None = None


class OwnedItemService:
    """Ingest one owned item without coupling the workflow to Telegram."""

    def __init__(
        self,
        *,
        repository: OwnedItemRepository,
        storage: ImageStorage,
        image_validator: ImageValidator,
        item_analysis: ItemAnalysisService,
        profile_service: ProfileService,
        pipeline: FeaturePipelineVersion,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._image_validator = image_validator
        self._item_analysis = item_analysis
        self._profile_service = profile_service
        self._pipeline = pipeline

    @property
    def max_upload_bytes(self) -> int:
        return self._image_validator.max_bytes

    async def create(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        filename: str | None,
        declared_mime_type: str | None,
        data: bytes,
        item_name: str | None,
    ) -> OwnedItemResult:
        image = self._image_validator.validate(data, declared_mime_type)

        try:
            user = self._repository.find_or_create_user(telegram_user_id, display_name)
            user_id = UUID(str(user["id"]))
        except Exception as error:
            raise OwnedItemPersistenceError("Could not resolve AURA user") from error

        item_id = uuid4()
        storage_path = f"users/{user_id}/items/{item_id}/original.{image.extension}"
        try:
            self._storage.upload(
                path=storage_path,
                data=image.original_data,
                mime_type=image.mime_type,
            )
        except Exception as error:
            raise OwnedItemStorageError("Could not store item image") from error

        try:
            created = self._repository.create_item_with_analysis(
                item_id=item_id,
                user_id=user_id,
                source=ItemSource.OWNED,
                storage_path=storage_path,
                original_filename=filename,
                mime_type=image.mime_type,
                size_bytes=image.size_bytes,
                width_px=image.width_px,
                height_px=image.height_px,
                content_sha256=image.content_sha256,
                item_name=item_name,
                pipeline=self._pipeline,
            )
            analysis_id = UUID(str(created["analysis_id"]))
        except Exception as error:
            try:
                self._storage.delete(storage_path)
            except Exception:
                pass
            raise OwnedItemPersistenceError("Could not persist owned item") from error

        analysis = await self._item_analysis.analyze(
            analysis_id=analysis_id,
            image=ImageInput(
                data=image.analysis_data,
                mime_type=image.mime_type,
                filename=filename,
            ),
        )
        try:
            profile_result = self._profile_service.rebuild_if_ready(user_id)
            profile_status = profile_result.status
            usable_item_count = profile_result.usable_item_count
            profile_id = profile_result.profile_id
        except (ProfileBuildError, ProfilePersistenceError):
            profile_status = "REBUILD_FAILED"
            usable_item_count = None
            profile_id = None
        return OwnedItemResult(
            item_id=item_id,
            analysis=analysis,
            profile_status=profile_status,
            usable_item_count=usable_item_count,
            profile_id=profile_id,
        )
