from __future__ import annotations

import base64
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from aura_backend.api.dependencies import get_suggestion_service
from aura_backend.application.suggestions import (
    SuggestionGenerationUnavailable,
    SuggestionCategory,
    SuggestionIntent,
    SuggestionPersistenceError,
    SuggestionProfileNotReady,
    SuggestionService,
)


router = APIRouter(prefix="/v1/suggestions", tags=["suggestions"])


class SuggestionRequest(BaseModel):
    intent: SuggestionIntent
    category: SuggestionCategory = SuggestionCategory.ANY
    count: int = Field(default=3, ge=1, le=3)
    exclude_labels: list[str] = Field(default_factory=list, max_length=5)


class SuggestedItemResponse(BaseModel):
    label: str
    rationale: str
    image_base64: str
    mime_type: str


class SuggestionResponse(BaseModel):
    intent: SuggestionIntent
    category: SuggestionCategory
    suggestions: list[SuggestedItemResponse]


@router.post("", response_model=SuggestionResponse)
async def create_suggestions(
    request: SuggestionRequest,
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[SuggestionService, Depends(get_suggestion_service)],
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> SuggestionResponse:
    """Generate transient profile-guided wardrobe reference images."""
    try:
        result = await service.generate(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            intent=request.intent,
            category=request.category,
            count=request.count,
            exclude_labels=request.exclude_labels,
        )
    except SuggestionProfileNotReady as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "PROFILE_NOT_READY") from error
    except SuggestionPersistenceError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SUGGESTION_PROCESSING_UNAVAILABLE",
        ) from error
    except SuggestionGenerationUnavailable as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "IMAGE_GENERATION_FAILED",
        ) from error

    return SuggestionResponse(
        intent=result.intent,
        category=result.category,
        suggestions=[
            SuggestedItemResponse(
                label=suggestion.label,
                rationale=suggestion.rationale,
                image_base64=base64.b64encode(suggestion.image.data).decode("ascii"),
                mime_type=suggestion.image.mime_type,
            )
            for suggestion in result.suggestions
        ],
    )
