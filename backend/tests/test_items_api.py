from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from aura_backend.api.dependencies import get_candidate_item_service, get_owned_item_service
from aura_backend.domain.models import (
    ColourObservation,
    ImageQuality,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    MatchComponentScore,
    MatchDimension,
    MatchResultV1,
)
from aura_backend.main import create_app

INTERNAL_API_KEY = "test-internal-api-key-1234567890"
AUTH_HEADERS = {"Authorization": f"Bearer {INTERNAL_API_KEY}"}


def make_features() -> ItemVisualFeaturesV1:
    return ItemVisualFeaturesV1(
        item_type=ItemTypeObservation(value="handbag", confidence=0.9),
        item_name="pink bag",
        colours=[
            ColourObservation(
                name="pink",
                hex="#FFC0CB",
                proportion=1.0,
                confidence=0.9,
            )
        ],
        quality=ImageQuality(usable=True, score=0.9),
        description="A pink bag.",
    )


class FakeOwnedItemService:
    max_upload_bytes = 1_000_000

    async def create(self, **_: object):
        analysis_id = uuid4()
        return SimpleNamespace(
            item_id=uuid4(),
            analysis=SimpleNamespace(analysis_id=analysis_id, features=make_features()),
            profile_status="COLLECTING",
            usable_item_count=1,
            profile_id=None,
        )


class FakeCandidateItemService:
    max_upload_bytes = 1_000_000

    async def create_and_match(self, **_: object):
        features = make_features()
        item_id = uuid4()
        profile_id = uuid4()
        match = MatchResultV1(
            candidate_item_id=item_id,
            profile_id=profile_id,
            overall_score=0.9,
            classification="STRONG_FIT",
            component_scores=[
                MatchComponentScore(
                    dimension=MatchDimension.COLOUR,
                    score=0.9,
                    effective_weight=1.0,
                    confidence=0.9,
                )
            ],
            explanation="Strong Fit. Based on your uploaded items.",
            scoring_version=1,
            explanation_version=1,
        )
        return SimpleNamespace(
            item_id=item_id,
            analysis=SimpleNamespace(analysis_id=uuid4(), features=features),
            match_id=uuid4(),
            match=match,
        )


def test_create_owned_item_returns_completed_analysis() -> None:
    app = create_app(internal_api_key=INTERNAL_API_KEY)
    app.dependency_overrides[get_owned_item_service] = lambda: FakeOwnedItemService()

    response = TestClient(app, headers=AUTH_HEADERS).post(
        "/v1/items/owned",
        headers={"X-Telegram-User-Id": "123"},
        files={"file": ("bag.png", b"image-bytes", "image/png")},
        data={"item_name": "Favorite bag"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "READY"
    assert response.json()["features"]["itemType"]["value"] == "handbag"
    assert response.json()["profile_status"] == "COLLECTING"
    assert response.json()["usable_item_count"] == 1


def test_create_owned_item_requires_telegram_identity() -> None:
    app = create_app(internal_api_key=INTERNAL_API_KEY)
    app.dependency_overrides[get_owned_item_service] = lambda: FakeOwnedItemService()

    response = TestClient(app, headers=AUTH_HEADERS).post(
        "/v1/items/owned",
        files={"file": ("bag.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 422


def test_create_candidate_item_returns_match_result() -> None:
    app = create_app(internal_api_key=INTERNAL_API_KEY)
    app.dependency_overrides[get_candidate_item_service] = lambda: FakeCandidateItemService()

    response = TestClient(app, headers=AUTH_HEADERS).post(
        "/v1/items/candidates",
        headers={"X-Telegram-User-Id": "123"},
        files={"file": ("candidate.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["match"]["classification"] == "STRONG_FIT"
    assert response.json()["match"]["scoringVersion"] == 1
