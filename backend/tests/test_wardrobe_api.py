from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from aura_backend.api.dependencies import get_wardrobe_service
from aura_backend.application.profiles import ProfileRebuildResult
from aura_backend.application.wardrobe import (
    CorrectionField,
    CorrectionPreview,
    CorrectionResult,
    WardrobeImage,
    WardrobeItemDetail,
    WardrobeItemSummary,
    WardrobePage,
)
from aura_backend.domain.models import (
    ColourObservation,
    ImageQuality,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
)
from aura_backend.main import create_app


ITEM_ID = uuid4()


def make_features() -> ItemVisualFeaturesV1:
    return ItemVisualFeaturesV1(
        item_type=ItemTypeObservation(value="bag", confidence=1.0),
        item_name="Black bag",
        colours=[
            ColourObservation(
                name="black",
                hex="#000000",
                proportion=1.0,
                confidence=1.0,
            )
        ],
        quality=ImageQuality(usable=True, score=1.0),
        description="A black bag.",
    )


class FakeWardrobeService:
    def list_items(self, **_: object) -> WardrobePage:
        return WardrobePage(
            items=[
                WardrobeItemSummary(
                    item_id=ITEM_ID,
                    label="Black bag",
                    created_at=datetime(2026, 10, 17, tzinfo=UTC),
                )
            ],
            page=1,
            page_size=10,
            has_previous=False,
            has_next=False,
        )

    def get_item(self, **_: object) -> WardrobeItemDetail:
        return WardrobeItemDetail(
            item_id=ITEM_ID,
            created_at=datetime(2026, 10, 17, tzinfo=UTC),
            features=make_features(),
            corrected_fields=[],
        )

    def get_image(self, **_: object) -> WardrobeImage:
        return WardrobeImage(data=b"jpeg", mime_type="image/jpeg")

    def preview_correction(self, **_: object) -> CorrectionPreview:
        return CorrectionPreview(
            item_id=ITEM_ID,
            field=CorrectionField.ITEM_NAME,
            features=make_features().model_copy(update={"item_name": "Travel bag"}),
        )

    async def apply_correction(self, **_: object) -> CorrectionResult:
        return CorrectionResult(
            item_id=ITEM_ID,
            field=CorrectionField.ITEM_NAME,
            features=make_features().model_copy(update={"item_name": "Travel bag"}),
            profile=ProfileRebuildResult(status="READY", usable_item_count=6),
        )


def test_wardrobe_api_lists_details_image_and_corrections() -> None:
    app = create_app()
    app.dependency_overrides[get_wardrobe_service] = lambda: FakeWardrobeService()
    client = TestClient(app)
    headers = {"X-Telegram-User-Id": "123"}

    listing = client.get("/v1/wardrobe", headers=headers)
    detail = client.get(f"/v1/wardrobe/items/{ITEM_ID}", headers=headers)
    image = client.get(f"/v1/wardrobe/items/{ITEM_ID}/image", headers=headers)
    preview = client.post(
        f"/v1/wardrobe/items/{ITEM_ID}/corrections/preview",
        headers=headers,
        json={"field": "item_name", "values": ["Travel bag"]},
    )
    saved = client.post(
        f"/v1/wardrobe/items/{ITEM_ID}/corrections",
        headers=headers,
        json={"field": "item_name", "values": ["Travel bag"]},
    )

    assert listing.status_code == 200
    assert listing.json()["items"][0]["label"] == "Black bag"
    assert detail.json()["features"]["itemName"] == "Black bag"
    assert image.content == b"jpeg"
    assert image.headers["content-type"] == "image/jpeg"
    assert preview.json()["features"]["itemName"] == "Travel bag"
    assert saved.json()["profile_status"] == "READY"


def test_correction_options_expose_typed_input_examples() -> None:
    response = TestClient(create_app()).get("/v1/wardrobe/correction-options")

    assert response.status_code == 200
    style = next(option for option in response.json() if option["field"] == "style_traits")
    assert "casual, minimal" in style["examples"]
    assert "separated by commas" in style["input_hint"]
