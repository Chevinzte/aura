from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from aura_backend.domain.models import FeedbackCategory, FeedbackType


class FeedbackRepository(Protocol):
    def find_user_by_telegram_id(self, telegram_user_id: int) -> dict[str, Any] | None: ...

    def match_belongs_to_user(self, *, match_id: UUID, user_id: UUID) -> bool: ...

    def upsert_feedback(self, **kwargs: Any) -> dict[str, Any]: ...


class FeedbackError(RuntimeError):
    """Base error for feedback capture."""


class FeedbackTargetNotFound(FeedbackError):
    """Raised when the user or completed match is unavailable."""


class FeedbackPersistenceError(FeedbackError):
    """Raised when feedback cannot be persisted."""


@dataclass(frozen=True, slots=True)
class FeedbackResult:
    feedback_id: UUID
    match_id: UUID
    category: FeedbackCategory
    feedback_type: FeedbackType
    note: str | None


class FeedbackService:
    """Capture explicit match feedback without changing profile weights."""

    def __init__(self, repository: FeedbackRepository) -> None:
        self._repository = repository

    def submit(
        self,
        *,
        telegram_user_id: int,
        match_id: UUID,
        feedback_type: FeedbackType,
        note: str | None,
    ) -> FeedbackResult:
        normalized_note = note.strip() if note and note.strip() else None
        category = self._category_for(feedback_type)
        try:
            user = self._repository.find_user_by_telegram_id(telegram_user_id)
        except Exception as error:
            raise FeedbackPersistenceError("Could not resolve AURA user") from error
        if user is None:
            raise FeedbackTargetNotFound("Feedback target does not exist")

        user_id = UUID(str(user["id"]))
        try:
            owns_match = self._repository.match_belongs_to_user(
                match_id=match_id,
                user_id=user_id,
            )
        except Exception as error:
            raise FeedbackPersistenceError("Could not verify match ownership") from error
        if not owns_match:
            raise FeedbackTargetNotFound("Feedback target does not exist")

        try:
            row = self._repository.upsert_feedback(
                user_id=user_id,
                match_id=match_id,
                category=category,
                feedback_type=feedback_type,
                note=normalized_note,
            )
            feedback_id = UUID(str(row["id"]))
        except Exception as error:
            raise FeedbackPersistenceError("Could not save feedback") from error

        return FeedbackResult(
            feedback_id=feedback_id,
            match_id=match_id,
            category=category,
            feedback_type=feedback_type,
            note=normalized_note,
        )

    def _category_for(self, feedback_type: FeedbackType) -> FeedbackCategory:
        if feedback_type in {FeedbackType.LIKE, FeedbackType.DISLIKE}:
            return FeedbackCategory.TASTE
        return FeedbackCategory.DECISION
