from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from aura_backend.ai.contracts import ImageInput
from aura_backend.application.item_analysis import ItemAnalysisResult, ItemAnalysisService
from aura_backend.application.matching import ActiveProfile, CandidateMatcher
from aura_backend.domain.models import ItemSource, MatchResultV1
from aura_backend.media.images import ImageValidator
from aura_backend.media.storage import ImageStorage
from aura_backend.repositories.supabase import FeaturePipelineVersion


class CandidateItemRepository(Protocol):
    def find_or_create_user(
        self, telegram_user_id: int, display_name: str | None
    ) -> dict[str, Any]: ...

    def get_active_profile(
        self, *, user_id: UUID, pipeline: FeaturePipelineVersion
    ) -> ActiveProfile | None: ...

    def create_item_with_analysis(self, **kwargs: Any) -> dict[str, Any]: ...

    def save_match_analysis(self, **kwargs: Any) -> dict[str, Any]: ...


class CandidateItemError(RuntimeError):
    """Base error for candidate-item evaluation."""


class ProfileNotReady(CandidateItemError):
    """Raised when the user has no compatible active profile."""


class CandidateStorageError(CandidateItemError):
    """Raised when the candidate image cannot be stored."""


class CandidatePersistenceError(CandidateItemError):
    """Raised when candidate or match data cannot be persisted."""


@dataclass(frozen=True, slots=True)
class CandidateItemResult:
    item_id: UUID
    analysis: ItemAnalysisResult
    match_id: UUID
    match: MatchResultV1


class CandidateItemService:
    """Analyze a candidate and compare it with the user's active profile."""

    def __init__(
        self,
        *,
        repository: CandidateItemRepository,
        storage: ImageStorage,
        image_validator: ImageValidator,
        item_analysis: ItemAnalysisService,
        matcher: CandidateMatcher,
        pipeline: FeaturePipelineVersion,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._image_validator = image_validator
        self._item_analysis = item_analysis
        self._matcher = matcher
        self._pipeline = pipeline

    @property
    def max_upload_bytes(self) -> int:
        return self._image_validator.max_bytes

    async def create_and_match(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        filename: str | None,
        declared_mime_type: str | None,
        data: bytes,
        item_name: str | None,
    ) -> CandidateItemResult:
        image = self._image_validator.validate(data, declared_mime_type)
        try:
            user = self._repository.find_or_create_user(telegram_user_id, display_name)
            user_id = UUID(str(user["id"]))
            active_profile = self._repository.get_active_profile(
                user_id=user_id,
                pipeline=self._pipeline,
            )
        except Exception as error:
            raise CandidatePersistenceError("Could not load candidate context") from error
        if active_profile is None:
            raise ProfileNotReady("A compatible active aesthetic profile is required")

        item_id = uuid4()
        storage_path = f"users/{user_id}/items/{item_id}/original.{image.extension}"
        try:
            self._storage.upload(
                path=storage_path,
                data=image.original_data,
                mime_type=image.mime_type,
            )
        except Exception as error:
            raise CandidateStorageError("Could not store candidate image") from error

        try:
            created = self._repository.create_item_with_analysis(
                item_id=item_id,
                user_id=user_id,
                source=ItemSource.CANDIDATE,
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
            raise CandidatePersistenceError("Could not persist candidate item") from error

        analysis = await self._item_analysis.analyze(
            analysis_id=analysis_id,
            image=ImageInput(
                data=image.analysis_data,
                mime_type=image.mime_type,
                filename=filename,
            ),
        )
        match = self._matcher.compare(
            candidate_item_id=item_id,
            profile_id=active_profile.profile_id,
            candidate_features=analysis.features,
            candidate_embedding=analysis.embedding,
            profile=active_profile.profile,
        )
        try:
            saved_match = self._repository.save_match_analysis(
                match_id=uuid4(),
                user_id=user_id,
                candidate_features_id=analysis_id,
                match=match,
            )
            match_id = UUID(str(saved_match["id"]))
        except Exception as error:
            raise CandidatePersistenceError("Could not persist candidate match") from error

        return CandidateItemResult(
            item_id=item_id,
            analysis=analysis,
            match_id=match_id,
            match=match,
        )
