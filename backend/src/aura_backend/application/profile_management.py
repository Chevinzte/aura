from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from aura_backend.application.profiles import (
    ProfileBuildError,
    ProfilePersistenceError,
    ProfileService,
)
from aura_backend.repositories.supabase import FeaturePipelineVersion


class ProfileManagementError(RuntimeError):
    """Base error for owned-item profile management."""


class ProfileItemNotFound(ProfileManagementError):
    """Raised when an owned item is missing or belongs to another user."""


class ProfileManagementPersistenceError(ProfileManagementError):
    """Raised when profile-management state cannot be loaded or changed."""


@dataclass(frozen=True, slots=True)
class ProfileItemSummary:
    item_id: UUID
    label: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProfileMutationResult:
    status: str
    usable_item_count: int
    removed_item_count: int


class ProfileManagementRepository(Protocol):
    def find_or_create_user(
        self, telegram_user_id: int, display_name: str | None
    ) -> dict[str, Any]: ...

    def list_owned_profile_items(
        self,
        *,
        user_id: UUID,
        pipeline: FeaturePipelineVersion,
        limit: int,
    ) -> list[ProfileItemSummary]: ...

    def remove_owned_item(self, *, user_id: UUID, item_id: UUID) -> None: ...

    def reset_owned_items(self, *, user_id: UUID) -> int: ...


class ProfileManagementService:
    """List and safely remove owned items that contribute to a profile."""

    def __init__(
        self,
        *,
        repository: ProfileManagementRepository,
        profile_service: ProfileService,
        pipeline: FeaturePipelineVersion,
    ) -> None:
        self._repository = repository
        self._profile_service = profile_service
        self._pipeline = pipeline

    def list_items(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        limit: int = 10,
    ) -> list[ProfileItemSummary]:
        user_id = self._resolve_user(telegram_user_id, display_name)
        try:
            return self._repository.list_owned_profile_items(
                user_id=user_id,
                pipeline=self._pipeline,
                limit=limit,
            )
        except Exception as error:
            raise ProfileManagementPersistenceError(
                "Could not list owned profile items"
            ) from error

    def remove_item(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
    ) -> ProfileMutationResult:
        user_id = self._resolve_user(telegram_user_id, display_name)
        try:
            items = self._repository.list_owned_profile_items(
                user_id=user_id,
                pipeline=self._pipeline,
                limit=100,
            )
            if not any(item.item_id == item_id for item in items):
                raise ProfileItemNotFound("Owned item does not exist")
            self._repository.remove_owned_item(
                user_id=user_id,
                item_id=item_id,
            )
        except ProfileItemNotFound:
            raise
        except Exception as error:
            raise ProfileManagementPersistenceError(
                "Could not remove owned profile item"
            ) from error

        try:
            rebuild = self._profile_service.rebuild_if_ready(user_id)
            return ProfileMutationResult(
                status=rebuild.status,
                usable_item_count=rebuild.usable_item_count,
                removed_item_count=1,
            )
        except (ProfileBuildError, ProfilePersistenceError):
            return ProfileMutationResult(
                status="REBUILD_FAILED",
                usable_item_count=max(0, len(items) - 1),
                removed_item_count=1,
            )

    def reset_profile(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
    ) -> ProfileMutationResult:
        user_id = self._resolve_user(telegram_user_id, display_name)
        try:
            removed_item_count = self._repository.reset_owned_items(user_id=user_id)
        except Exception as error:
            raise ProfileManagementPersistenceError(
                "Could not reset aesthetic profile"
            ) from error
        return ProfileMutationResult(
            status="COLLECTING",
            usable_item_count=0,
            removed_item_count=removed_item_count,
        )

    def _resolve_user(self, telegram_user_id: int, display_name: str | None) -> UUID:
        try:
            user = self._repository.find_or_create_user(telegram_user_id, display_name)
            return UUID(str(user["id"]))
        except Exception as error:
            raise ProfileManagementPersistenceError("Could not resolve AURA user") from error
