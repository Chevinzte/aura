from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aura_backend.application.profile_management import (
    ProfileItemNotFound,
    ProfileItemSummary,
    ProfileManagementService,
)
from aura_backend.repositories.supabase import FeaturePipelineVersion


PIPELINE = FeaturePipelineVersion(
    vision_provider="gateway",
    vision_model="vision-model",
    vision_prompt_version=1,
    feature_schema_version=1,
    embedding_provider="gateway",
    embedding_model="embedding-model",
    embedding_dimensions=2,
    embedding_schema_version=1,
)


class FakeRepository:
    def __init__(self) -> None:
        self.user_id = uuid4()
        self.items = [
            ProfileItemSummary(
                item_id=uuid4(),
                label=f"Item {index}",
                created_at=datetime(2026, 10, index + 1, tzinfo=UTC),
            )
            for index in range(6)
        ]
        self.removed_item_id = None

    def find_or_create_user(self, _: int, __: str | None):
        return {"id": str(self.user_id)}

    def list_owned_profile_items(self, **_: object):
        return self.items

    def remove_owned_item(self, *, user_id, item_id):
        assert user_id == self.user_id
        self.removed_item_id = item_id

    def reset_owned_items(self, *, user_id):
        assert user_id == self.user_id
        return len(self.items)


class FakeProfileService:
    def rebuild_if_ready(self, user_id):
        return SimpleNamespace(status="READY", usable_item_count=5)


def make_service(repository: FakeRepository):
    return ProfileManagementService(
        repository=repository,  # type: ignore[arg-type]
        profile_service=FakeProfileService(),  # type: ignore[arg-type]
        pipeline=PIPELINE,
    )


def test_remove_owned_item_rebuilds_profile() -> None:
    repository = FakeRepository()
    item = repository.items[0]

    result = make_service(repository).remove_item(
        telegram_user_id=123,
        display_name="Vinz",
        item_id=item.item_id,
    )

    assert repository.removed_item_id == item.item_id
    assert result.status == "READY"
    assert result.usable_item_count == 5


def test_remove_owned_item_hides_missing_or_unowned_item() -> None:
    repository = FakeRepository()

    with pytest.raises(ProfileItemNotFound):
        make_service(repository).remove_item(
            telegram_user_id=123,
            display_name=None,
            item_id=uuid4(),
        )

    assert repository.removed_item_id is None


def test_reset_profile_soft_deletes_all_owned_items() -> None:
    repository = FakeRepository()

    result = make_service(repository).reset_profile(
        telegram_user_id=123,
        display_name="Vinz",
    )

    assert result.status == "COLLECTING"
    assert result.usable_item_count == 0
    assert result.removed_item_count == 6
