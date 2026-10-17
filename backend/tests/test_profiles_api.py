from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from aura_backend.api.dependencies import (
    get_profile_management_service,
    get_profile_read_service,
)
from aura_backend.application.profile_management import (
    ProfileItemNotFound,
    ProfileItemPage,
    ProfileItemSummary,
    ProfileMutationResult,
)
from aura_backend.application.profiles import ProfileDisplay, ProfilePersistenceError
from aura_backend.main import create_app


class FakeProfileReadService:
    def get(self, **_: object):
        return SimpleNamespace(
            status="READY",
            display_name="Vinz",
            usable_item_count=6,
            minimum_item_count=5,
            profile=ProfileDisplay(
                colours=["cream", "black"],
                style_traits=["minimal"],
                patterns=["plain"],
                materials=["cotton"],
                textures=[],
                shape_traits=["structured"],
                decorative_details=[],
                style_influences=["quiet luxury"],
                summary="Your uploaded belongings suggest a minimal profile.",
            ),
            generated_at=None,
        )


class FakeProfileManagementService:
    def __init__(self) -> None:
        self.item_id = uuid4()

    def list_items(self, **_: object):
        return ProfileItemPage(
            items=[
                ProfileItemSummary(
                    item_id=self.item_id,
                    label="Favorite bag",
                    created_at=datetime(2026, 10, 16, tzinfo=UTC),
                )
            ],
            page=1,
            page_size=10,
            has_previous=False,
            has_next=True,
        )

    def remove_item(self, **_: object):
        return ProfileMutationResult(
            status="COLLECTING",
            usable_item_count=4,
            removed_item_count=1,
        )

    def reset_profile(self, **_: object):
        return ProfileMutationResult(
            status="COLLECTING",
            usable_item_count=0,
            removed_item_count=5,
        )


def test_get_profile_returns_display_safe_profile() -> None:
    app = create_app()
    app.dependency_overrides[get_profile_read_service] = lambda: FakeProfileReadService()

    response = TestClient(app).get(
        "/v1/profile",
        headers={
            "X-Telegram-User-Id": "123",
            "X-Telegram-Display-Name": "Vinz",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert response.json()["profile"]["colours"] == ["cream", "black"]
    assert "embedding" not in response.text
    assert "profile_id" not in response.text


def test_get_profile_maps_persistence_failure() -> None:
    class FailingService:
        def get(self, **_: object):
            raise ProfilePersistenceError("failed")

    app = create_app()
    app.dependency_overrides[get_profile_read_service] = lambda: FailingService()

    response = TestClient(app).get(
        "/v1/profile",
        headers={"X-Telegram-User-Id": "123"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "PROFILE_READ_UNAVAILABLE"


def test_profile_management_endpoints_list_remove_and_reset() -> None:
    service = FakeProfileManagementService()
    app = create_app()
    app.dependency_overrides[get_profile_management_service] = lambda: service
    client = TestClient(app)
    headers = {"X-Telegram-User-Id": "123"}

    listed = client.get("/v1/profile/items", headers=headers)
    removed = client.delete(f"/v1/profile/items/{service.item_id}", headers=headers)
    reset = client.delete("/v1/profile", headers=headers)

    assert listed.status_code == 200
    assert listed.json()["items"][0]["label"] == "Favorite bag"
    assert listed.json()["has_next"] is True
    assert removed.status_code == 200
    assert removed.json()["usable_item_count"] == 4
    assert reset.status_code == 200
    assert reset.json()["removed_item_count"] == 5


def test_remove_profile_item_hides_missing_item() -> None:
    class MissingService(FakeProfileManagementService):
        def remove_item(self, **_: object):
            raise ProfileItemNotFound("missing")

    app = create_app()
    app.dependency_overrides[get_profile_management_service] = lambda: MissingService()

    response = TestClient(app).delete(
        f"/v1/profile/items/{uuid4()}",
        headers={"X-Telegram-User-Id": "123"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "OWNED_ITEM_NOT_FOUND"
