from fastapi.testclient import TestClient

from aura_backend.api.dependencies import get_preference_service
from aura_backend.application.preferences import (
    FashionPresentation,
    UserPreferences,
)
from aura_backend.main import create_app

INTERNAL_API_KEY = "test-internal-api-key-1234567890"
AUTH_HEADERS = {"Authorization": f"Bearer {INTERNAL_API_KEY}"}


class FakePreferenceService:
    def get(self, **kwargs: object) -> UserPreferences:
        assert kwargs["telegram_user_id"] == 123
        return UserPreferences(fashion_presentation=None)

    def set_fashion_presentation(self, **kwargs: object) -> UserPreferences:
        assert kwargs["telegram_user_id"] == 123
        assert kwargs["fashion_presentation"] == FashionPresentation.MENSWEAR
        return UserPreferences(fashion_presentation=FashionPresentation.MENSWEAR)


def test_preferences_api_reads_and_updates_fashion_presentation() -> None:
    app = create_app(internal_api_key=INTERNAL_API_KEY)
    app.dependency_overrides[get_preference_service] = lambda: FakePreferenceService()
    client = TestClient(app, headers=AUTH_HEADERS)

    response = client.get(
        "/v1/preferences",
        headers={"X-Telegram-User-Id": "123"},
    )
    updated = client.put(
        "/v1/preferences/fashion-presentation",
        headers={"X-Telegram-User-Id": "123"},
        json={"fashion_presentation": "MENSWEAR"},
    )

    assert response.status_code == 200
    assert response.json() == {"fashion_presentation": None}
    assert updated.status_code == 200
    assert updated.json() == {"fashion_presentation": "MENSWEAR"}
