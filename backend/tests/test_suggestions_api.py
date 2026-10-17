from fastapi.testclient import TestClient

from aura_backend.ai.contracts import GeneratedImage
from aura_backend.api.dependencies import get_suggestion_service
from aura_backend.application.suggestions import (
    SuggestionCategory,
    SuggestionIntent,
    SuggestionProfileNotReady,
    SuggestionResult,
    WardrobeSuggestion,
)
from aura_backend.main import create_app


class FakeSuggestionService:
    async def generate(self, **kwargs: object) -> SuggestionResult:
        assert kwargs["telegram_user_id"] == 123
        assert kwargs["intent"] == SuggestionIntent.SAFE_EXTENSION
        assert kwargs["category"] == SuggestionCategory.TOPS
        return SuggestionResult(
            intent=SuggestionIntent.SAFE_EXTENSION,
            category=SuggestionCategory.TOPS,
            suggestions=[
                WardrobeSuggestion(
                    label="Fine-knit cardigan",
                    rationale="Extends your minimal preferences.",
                    image=GeneratedImage(data=b"jpeg", mime_type="image/jpeg"),
                )
            ],
        )


def test_suggestion_api_returns_transient_image_payload() -> None:
    app = create_app()
    app.dependency_overrides[get_suggestion_service] = lambda: FakeSuggestionService()

    response = TestClient(app).post(
        "/v1/suggestions",
        headers={"X-Telegram-User-Id": "123"},
        json={
            "intent": "SAFE_EXTENSION",
            "category": "TOPS",
            "count": 1,
            "exclude_labels": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["category"] == "TOPS"
    assert response.json()["suggestions"][0]["image_base64"] == "anBlZw=="
    assert response.json()["suggestions"][0]["mime_type"] == "image/jpeg"


def test_suggestion_api_maps_profile_not_ready() -> None:
    class NotReadyService:
        async def generate(self, **_: object):
            raise SuggestionProfileNotReady("not ready")

    app = create_app()
    app.dependency_overrides[get_suggestion_service] = lambda: NotReadyService()
    response = TestClient(app).post(
        "/v1/suggestions",
        headers={"X-Telegram-User-Id": "123"},
        json={"intent": "SURPRISE_ME", "count": 3},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "PROFILE_NOT_READY"
