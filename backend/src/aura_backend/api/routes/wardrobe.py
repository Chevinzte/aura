from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from aura_backend.api.dependencies import get_wardrobe_service
from aura_backend.application.wardrobe import (
    CORRECTION_EXAMPLES,
    CorrectionField,
    InvalidCorrection,
    WardrobeItemNotFound,
    WardrobePersistenceError,
    WardrobeService,
)
from aura_backend.domain.models import ItemVisualFeaturesV1


router = APIRouter(prefix="/v1/wardrobe", tags=["wardrobe"])


class WardrobeItemSummaryResponse(BaseModel):
    item_id: UUID
    label: str
    created_at: datetime


class WardrobePageResponse(BaseModel):
    items: list[WardrobeItemSummaryResponse]
    page: int
    page_size: int
    has_previous: bool
    has_next: bool


class WardrobeItemResponse(BaseModel):
    item_id: UUID
    created_at: datetime
    features: ItemVisualFeaturesV1
    corrected_fields: list[CorrectionField]


class CorrectionRequest(BaseModel):
    field: CorrectionField
    values: list[str] = Field(min_length=1, max_length=8)


class CorrectionPreviewResponse(BaseModel):
    item_id: UUID
    field: CorrectionField
    features: ItemVisualFeaturesV1


class CorrectionResultResponse(CorrectionPreviewResponse):
    profile_status: str
    usable_item_count: int


class CorrectionOptionResponse(BaseModel):
    field: CorrectionField
    input_hint: str
    examples: list[str] = Field(default_factory=list)


@router.get("/correction-options", response_model=list[CorrectionOptionResponse])
def get_correction_options() -> list[CorrectionOptionResponse]:
    hints = {
        CorrectionField.ITEM_NAME: "Send one corrected item name.",
        CorrectionField.ITEM_TYPE: "Send one item type. Common terms are normalized automatically.",
        CorrectionField.COLOURS: (
            "Send one or more colour names separated by commas. AURA assigns "
            "standard colour values automatically."
        ),
        CorrectionField.PATTERNS: "Send one or more patterns separated by commas.",
        CorrectionField.MATERIALS: "Send one or more materials separated by commas.",
        CorrectionField.TEXTURES: "Send one or more textures separated by commas.",
        CorrectionField.STYLE_TRAITS: "Send one or more style traits separated by commas.",
        CorrectionField.SHAPE_TRAITS: "Send one or more shape traits separated by commas.",
        CorrectionField.DECORATIVE_DETAILS: (
            "Send one or more decorative details separated by commas."
        ),
    }
    return [
        CorrectionOptionResponse(
            field=field,
            input_hint=hints[field],
            examples=CORRECTION_EXAMPLES[field],
        )
        for field in CorrectionField
    ]


@router.get("", response_model=WardrobePageResponse)
def list_wardrobe_items(
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[WardrobeService, Depends(get_wardrobe_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> WardrobePageResponse:
    try:
        result = service.list_items(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            page=page,
        )
    except WardrobePersistenceError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "WARDROBE_UNAVAILABLE",
        ) from error
    return WardrobePageResponse(
        items=[
            WardrobeItemSummaryResponse(
                item_id=item.item_id,
                label=item.label,
                created_at=item.created_at,
            )
            for item in result.items
        ],
        page=result.page,
        page_size=result.page_size,
        has_previous=result.has_previous,
        has_next=result.has_next,
    )


@router.get("/items/{item_id}", response_model=WardrobeItemResponse)
def get_wardrobe_item(
    item_id: UUID,
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[WardrobeService, Depends(get_wardrobe_service)],
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> WardrobeItemResponse:
    try:
        item = service.get_item(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            item_id=item_id,
        )
    except WardrobeItemNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "WARDROBE_ITEM_NOT_FOUND") from error
    except WardrobePersistenceError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "WARDROBE_UNAVAILABLE",
        ) from error
    return WardrobeItemResponse(
        item_id=item.item_id,
        created_at=item.created_at,
        features=item.features,
        corrected_fields=item.corrected_fields,
    )


@router.get("/items/{item_id}/image")
def get_wardrobe_item_image(
    item_id: UUID,
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[WardrobeService, Depends(get_wardrobe_service)],
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> Response:
    try:
        image = service.get_image(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            item_id=item_id,
        )
    except WardrobeItemNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "WARDROBE_ITEM_NOT_FOUND") from error
    except WardrobePersistenceError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "WARDROBE_UNAVAILABLE",
        ) from error
    return Response(content=image.data, media_type=image.mime_type)


@router.post(
    "/items/{item_id}/corrections/preview",
    response_model=CorrectionPreviewResponse,
)
def preview_item_correction(
    item_id: UUID,
    request: CorrectionRequest,
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[WardrobeService, Depends(get_wardrobe_service)],
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> CorrectionPreviewResponse:
    try:
        preview = service.preview_correction(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            item_id=item_id,
            field=request.field,
            values=request.values,
        )
    except WardrobeItemNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "WARDROBE_ITEM_NOT_FOUND") from error
    except InvalidCorrection as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except WardrobePersistenceError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "WARDROBE_UNAVAILABLE",
        ) from error
    return CorrectionPreviewResponse(
        item_id=preview.item_id,
        field=preview.field,
        features=preview.features,
    )


@router.post(
    "/items/{item_id}/corrections",
    response_model=CorrectionResultResponse,
)
async def apply_item_correction(
    item_id: UUID,
    request: CorrectionRequest,
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[WardrobeService, Depends(get_wardrobe_service)],
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> CorrectionResultResponse:
    try:
        result = await service.apply_correction(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            item_id=item_id,
            field=request.field,
            values=request.values,
        )
    except WardrobeItemNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "WARDROBE_ITEM_NOT_FOUND") from error
    except InvalidCorrection as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except WardrobePersistenceError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "WARDROBE_CORRECTION_UNAVAILABLE",
        ) from error
    return CorrectionResultResponse(
        item_id=result.item_id,
        field=result.field,
        features=result.features,
        profile_status=result.profile.status,
        usable_item_count=result.profile.usable_item_count,
    )
