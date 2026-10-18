from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from aura_backend.api.dependencies import get_feedback_service
from aura_backend.domain.models import FeedbackCategory, FeedbackType
from aura_backend.main import create_app

INTERNAL_API_KEY = "test-internal-api-key-1234567890"
AUTH_HEADERS = {"Authorization": f"Bearer {INTERNAL_API_KEY}"}


class FakeFeedbackService:
    def submit(self, *, match_id, feedback_type, note, **_: object):
        return SimpleNamespace(
            feedback_id=uuid4(),
            match_id=match_id,
            category=FeedbackCategory.TASTE,
            feedback_type=feedback_type,
            note=note,
        )


def test_feedback_endpoint_returns_saved_feedback() -> None:
    app = create_app(internal_api_key=INTERNAL_API_KEY)
    app.dependency_overrides[get_feedback_service] = lambda: FakeFeedbackService()
    match_id = uuid4()

    response = TestClient(app, headers=AUTH_HEADERS).post(
        f"/v1/matches/{match_id}/feedback",
        headers={"X-Telegram-User-Id": "123"},
        json={"feedback_type": FeedbackType.LIKE, "note": "Accurate"},
    )

    assert response.status_code == 200
    assert response.json()["match_id"] == str(match_id)
    assert response.json()["category"] == "TASTE"
    assert response.json()["feedback_type"] == "LIKE"


def test_feedback_endpoint_rejects_unknown_type() -> None:
    app = create_app(internal_api_key=INTERNAL_API_KEY)
    app.dependency_overrides[get_feedback_service] = lambda: FakeFeedbackService()

    response = TestClient(app, headers=AUTH_HEADERS).post(
        f"/v1/matches/{uuid4()}/feedback",
        headers={"X-Telegram-User-Id": "123"},
        json={"feedback_type": "MAYBE"},
    )

    assert response.status_code == 422
