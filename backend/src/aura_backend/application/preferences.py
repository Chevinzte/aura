from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID


class FashionPresentation(StrEnum):
    MENSWEAR = "MENSWEAR"
    WOMENSWEAR = "WOMENSWEAR"
    GENDER_NEUTRAL = "GENDER_NEUTRAL"
    NO_PREFERENCE = "NO_PREFERENCE"


class PreferencePersistenceError(RuntimeError):
    """Raised when user preferences cannot be loaded or saved."""


@dataclass(frozen=True, slots=True)
class UserPreferences:
    fashion_presentation: FashionPresentation | None


class PreferenceRepository(Protocol):
    def find_or_create_user(
        self, telegram_user_id: int, display_name: str | None
    ) -> dict[str, Any]: ...

    def update_user_fashion_presentation(
        self,
        *,
        user_id: UUID,
        fashion_presentation: FashionPresentation,
    ) -> dict[str, Any]: ...


class PreferenceService:
    """Read and update optional user-controlled personalization settings."""

    def __init__(self, repository: PreferenceRepository) -> None:
        self._repository = repository

    def get(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
    ) -> UserPreferences:
        try:
            user = self._repository.find_or_create_user(telegram_user_id, display_name)
            preference = parse_fashion_presentation(user.get("fashion_presentation"))
        except Exception as error:
            raise PreferencePersistenceError("Could not load user preferences") from error
        return UserPreferences(fashion_presentation=preference)

    def set_fashion_presentation(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        fashion_presentation: FashionPresentation,
    ) -> UserPreferences:
        try:
            user = self._repository.find_or_create_user(telegram_user_id, display_name)
            updated = self._repository.update_user_fashion_presentation(
                user_id=UUID(str(user["id"])),
                fashion_presentation=fashion_presentation,
            )
            preference = parse_fashion_presentation(
                updated.get("fashion_presentation")
            )
        except Exception as error:
            raise PreferencePersistenceError("Could not save user preferences") from error
        if preference is None:
            raise PreferencePersistenceError("Saved user preference was unavailable")
        return UserPreferences(fashion_presentation=preference)


def parse_fashion_presentation(value: object) -> FashionPresentation | None:
    try:
        return FashionPresentation(value) if isinstance(value, str) else None
    except ValueError:
        return None
