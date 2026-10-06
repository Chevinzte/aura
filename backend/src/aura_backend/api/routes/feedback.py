from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from aura_backend.api.dependencies import get_feedback_service
from aura_backend.application.feedback import (
    FeedbackPersistenceError,
    FeedbackService,
    FeedbackTargetNotFound,
)
from aura_backend.domain.models import FeedbackCategory, FeedbackType


router = APIRouter(prefix="/v1/matches", tags=["feedback"])


class FeedbackRequest(BaseModel):
    feedback_type: FeedbackType
    note: str | None = Field(default=None, max_length=500)


class FeedbackResponse(BaseModel):
    feedback_id: UUID
    match_id: UUID
    category: FeedbackCategory
    feedback_type: FeedbackType
    note: str | None


@router.post("/{match_id}/feedback", response_model=FeedbackResponse)
def submit_feedback(
    match_id: UUID,
    request: FeedbackRequest,
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
) -> FeedbackResponse:
    """Create or replace feedback for the type's category."""
    try:
        result = service.submit(
            telegram_user_id=telegram_user_id,
            match_id=match_id,
            feedback_type=request.feedback_type,
            note=request.note,
        )
    except FeedbackTargetNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MATCH_NOT_FOUND") from error
    except FeedbackPersistenceError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "FEEDBACK_UNAVAILABLE",
        ) from error

    return FeedbackResponse(
        feedback_id=result.feedback_id,
        match_id=result.match_id,
        category=result.category,
        feedback_type=result.feedback_type,
        note=result.note,
    )
