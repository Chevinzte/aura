from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from aura_backend.api.dependencies import get_preference_service
from aura_backend.application.preferences import (
    FashionPresentation,
    PreferencePersistenceError,
    PreferenceService,
)


router = APIRouter(prefix="/v1/preferences", tags=["preferences"])


class PreferenceResponse(BaseModel):
    fashion_presentation: FashionPresentation | None


class FashionPresentationRequest(BaseModel):
    fashion_presentation: FashionPresentation


@router.get("", response_model=PreferenceResponse)
def get_preferences(
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[PreferenceService, Depends(get_preference_service)],
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> PreferenceResponse:
    """Return optional user-controlled personalization settings."""
    try:
        preferences = service.get(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
        )
    except PreferencePersistenceError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "PREFERENCES_UNAVAILABLE",
        ) from error
    return PreferenceResponse(
        fashion_presentation=preferences.fashion_presentation,
    )


@router.put("/fashion-presentation", response_model=PreferenceResponse)
def update_fashion_presentation(
    request: FashionPresentationRequest,
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[PreferenceService, Depends(get_preference_service)],
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> PreferenceResponse:
    """Save the presentation preference used for generated clothing ideas."""
    try:
        preferences = service.set_fashion_presentation(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            fashion_presentation=request.fashion_presentation,
        )
    except PreferencePersistenceError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "PREFERENCES_UNAVAILABLE",
        ) from error
    return PreferenceResponse(
        fashion_presentation=preferences.fashion_presentation,
    )
