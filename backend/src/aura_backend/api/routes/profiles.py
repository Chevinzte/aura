from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from aura_backend.api.dependencies import get_profile_read_service
from aura_backend.application.profiles import ProfilePersistenceError, ProfileReadService


router = APIRouter(prefix="/v1/profile", tags=["profiles"])


class ProfileDetailsResponse(BaseModel):
    colours: list[str]
    style_traits: list[str]
    patterns: list[str]
    materials: list[str]
    textures: list[str]
    shape_traits: list[str]
    decorative_details: list[str]
    style_influences: list[str]
    summary: str


class ProfileResponse(BaseModel):
    status: Literal["COLLECTING", "READY", "UNAVAILABLE"]
    display_name: str | None
    usable_item_count: int
    minimum_item_count: int
    profile: ProfileDetailsResponse | None = None
    generated_at: datetime | None = None


@router.get("", response_model=ProfileResponse)
def get_profile(
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[ProfileReadService, Depends(get_profile_read_service)],
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> ProfileResponse:
    """Return profile progress or a display-safe active profile summary."""
    try:
        result = service.get(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
        )
    except ProfilePersistenceError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "PROFILE_READ_UNAVAILABLE",
        ) from error

    profile = (
        ProfileDetailsResponse(**asdict(result.profile))
        if result.profile is not None
        else None
    )
    return ProfileResponse(
        status=result.status,
        display_name=result.display_name,
        usable_item_count=result.usable_item_count,
        minimum_item_count=result.minimum_item_count,
        profile=profile,
        generated_at=result.generated_at,
    )
