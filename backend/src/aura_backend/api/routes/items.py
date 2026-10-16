from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel

from aura_backend.application.candidate_items import (
    CandidateItemService,
    CandidatePersistenceError,
    CandidateStorageError,
    ProfileNotReady,
)
from aura_backend.application.item_analysis import (
    ItemAnalysisFailed,
    ItemAnalysisPersistenceError,
)
from aura_backend.application.matching import MatchBuildError
from aura_backend.application.owned_items import (
    OwnedItemPersistenceError,
    OwnedItemService,
    OwnedItemStorageError,
)
from aura_backend.api.dependencies import get_candidate_item_service, get_owned_item_service
from aura_backend.domain.models import ItemVisualFeaturesV1, MatchResultV1
from aura_backend.media.images import ImageTooLarge, ImageValidationError


router = APIRouter(prefix="/v1/items", tags=["items"])


class OwnedItemResponse(BaseModel):
    item_id: UUID
    analysis_id: UUID
    status: Literal["READY"] = "READY"
    features: ItemVisualFeaturesV1
    profile_status: Literal["COLLECTING", "READY", "REBUILD_FAILED"]
    usable_item_count: int | None = None
    minimum_item_count: int = 5
    profile_id: UUID | None = None


class CandidateItemResponse(BaseModel):
    item_id: UUID
    analysis_id: UUID
    match_id: UUID
    status: Literal["READY"] = "READY"
    features: ItemVisualFeaturesV1
    match: MatchResultV1


@router.post("/owned", response_model=OwnedItemResponse, status_code=status.HTTP_201_CREATED)
async def create_owned_item(
    file: Annotated[UploadFile, File()],
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[OwnedItemService, Depends(get_owned_item_service)],
    item_name: Annotated[str | None, Form(max_length=200)] = None,
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> OwnedItemResponse:
    """Store and analyze one belonging for the user's aesthetic profile."""
    try:
        result = await service.create(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            filename=file.filename,
            declared_mime_type=file.content_type,
            data=await file.read(service.max_upload_bytes + 1),
            item_name=item_name,
        )
    except ImageTooLarge as error:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, error.code) from error
    except ImageValidationError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, error.code) from error
    except ItemAnalysisFailed as error:
        response_status = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if error.error_code == "IMAGE_UNUSABLE"
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(response_status, error.error_code) from error
    except (OwnedItemStorageError, OwnedItemPersistenceError, ItemAnalysisPersistenceError) as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ITEM_PROCESSING_UNAVAILABLE") from error

    return OwnedItemResponse(
        item_id=result.item_id,
        analysis_id=result.analysis.analysis_id,
        features=result.analysis.features,
        profile_status=result.profile_status,
        usable_item_count=result.usable_item_count,
        profile_id=result.profile_id,
    )


@router.post(
    "/candidates",
    response_model=CandidateItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_candidate_item(
    file: Annotated[UploadFile, File()],
    telegram_user_id: Annotated[int, Header(alias="X-Telegram-User-Id")],
    service: Annotated[CandidateItemService, Depends(get_candidate_item_service)],
    item_name: Annotated[str | None, Form(max_length=200)] = None,
    display_name: Annotated[
        str | None, Header(alias="X-Telegram-Display-Name", max_length=200)
    ] = None,
) -> CandidateItemResponse:
    """Analyze a candidate item and compare it with the active profile."""
    try:
        result = await service.create_and_match(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            filename=file.filename,
            declared_mime_type=file.content_type,
            data=await file.read(service.max_upload_bytes + 1),
            item_name=item_name,
        )
    except ImageTooLarge as error:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, error.code) from error
    except ImageValidationError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, error.code) from error
    except ProfileNotReady as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "PROFILE_NOT_READY") from error
    except MatchBuildError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "PROFILE_INCOMPATIBLE") from error
    except ItemAnalysisFailed as error:
        response_status = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if error.error_code == "IMAGE_UNUSABLE"
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(response_status, error.error_code) from error
    except (
        CandidateStorageError,
        CandidatePersistenceError,
        ItemAnalysisPersistenceError,
    ) as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CANDIDATE_PROCESSING_UNAVAILABLE",
        ) from error

    return CandidateItemResponse(
        item_id=result.item_id,
        analysis_id=result.analysis.analysis_id,
        match_id=result.match_id,
        features=result.analysis.features,
        match=result.match,
    )
