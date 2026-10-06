from __future__ import annotations

from asyncio import run
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image

from aura_backend.application.owned_items import OwnedItemPersistenceError, OwnedItemService
from aura_backend.media.images import ImageValidator
from aura_backend.repositories.supabase import FeaturePipelineVersion


class FakeRepository:
    def __init__(self, *, fail_create: bool = False) -> None:
        self.user_id = uuid4()
        self.analysis_id = uuid4()
        self.fail_create = fail_create
        self.create_args: dict[str, object] | None = None

    def find_or_create_user(self, telegram_user_id: int, display_name: str | None) -> dict:
        return {"id": str(self.user_id)}

    def create_item_with_analysis(self, **kwargs: object) -> dict:
        self.create_args = kwargs
        if self.fail_create:
            raise RuntimeError("database unavailable")
        return {"item_id": str(kwargs["item_id"]), "analysis_id": str(self.analysis_id)}


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded_path: str | None = None
        self.deleted_path: str | None = None

    def upload(self, *, path: str, data: bytes, mime_type: str) -> None:
        self.uploaded_path = path

    def delete(self, path: str) -> None:
        self.deleted_path = path


class FakeAnalysisService:
    def __init__(self) -> None:
        self.image = None

    async def analyze(self, *, analysis_id, image):
        self.image = image
        return SimpleNamespace(analysis_id=analysis_id)


class FakeProfileService:
    def rebuild_if_ready(self, user_id):
        return SimpleNamespace(status="COLLECTING", profile_id=None)


def make_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (300, 300), "pink").save(output, format="PNG")
    return output.getvalue()


def make_service(repository: FakeRepository, storage: FakeStorage) -> OwnedItemService:
    return OwnedItemService(
        repository=repository,
        storage=storage,
        image_validator=ImageValidator(max_bytes=1_000_000, min_dimension=256),
        item_analysis=FakeAnalysisService(),  # type: ignore[arg-type]
        profile_service=FakeProfileService(),  # type: ignore[arg-type]
        pipeline=FeaturePipelineVersion(
            vision_provider="ai_lodge",
            vision_model="vision-model",
            vision_prompt_version=1,
            feature_schema_version=1,
            embedding_provider="ai_lodge",
            embedding_model="embedding-model",
            embedding_dimensions=1536,
            embedding_schema_version=1,
        ),
    )


def test_owned_item_uploads_persists_and_analyzes() -> None:
    repository = FakeRepository()
    storage = FakeStorage()

    result = run(
        make_service(repository, storage).create(
            telegram_user_id=123,
            display_name="AURA User",
            filename="bag.png",
            declared_mime_type="image/png",
            data=make_png(),
            item_name="Favorite bag",
        )
    )

    assert result.analysis.analysis_id == repository.analysis_id
    assert storage.uploaded_path is not None
    assert str(repository.user_id) in storage.uploaded_path
    assert repository.create_args is not None
    assert repository.create_args["storage_path"] == storage.uploaded_path
    assert result.profile_status == "COLLECTING"


def test_owned_item_deletes_upload_when_database_creation_fails() -> None:
    repository = FakeRepository(fail_create=True)
    storage = FakeStorage()

    with pytest.raises(OwnedItemPersistenceError):
        run(
            make_service(repository, storage).create(
                telegram_user_id=123,
                display_name=None,
                filename="bag.png",
                declared_mime_type="image/png",
                data=make_png(),
                item_name=None,
            )
        )

    assert storage.deleted_path == storage.uploaded_path
