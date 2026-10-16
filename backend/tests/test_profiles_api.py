from types import SimpleNamespace

from fastapi.testclient import TestClient

from aura_backend.api.dependencies import get_profile_read_service
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
