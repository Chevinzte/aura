from asyncio import run
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aura_backend.application.profiles import ProfileRebuildResult
from aura_backend.application.wardrobe import (
    CorrectionField,
    InvalidCorrection,
    WardrobeItemRecord,
    WardrobeItemSummary,
    WardrobePersistenceError,
    WardrobeService,
)
from aura_backend.domain.models import (
    ColourObservation,
    ImageQuality,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    SemanticEmbedding,
    StyleTraitObservation,
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


def make_features() -> ItemVisualFeaturesV1:
    return ItemVisualFeaturesV1(
        item_type=ItemTypeObservation(value="shirt", confidence=0.9),
        item_name="Blue shirt",
        colours=[
            ColourObservation(
                name="blue",
                hex="#0000FF",
                proportion=1.0,
                confidence=0.9,
            )
        ],
        style_traits=[StyleTraitObservation(value="casual", confidence=0.9)],
        quality=ImageQuality(usable=True, score=0.9),
        description="A blue shirt.",
    )


class FakeRepository:
    def __init__(self) -> None:
        self.user_id = uuid4()
        self.item_id = uuid4()
        self.feature_id = uuid4()
        self.previous_correction_id = uuid4()
        self.activated: dict[str, object] | None = None
        self.restored: dict[str, object] | None = None

    def find_or_create_user(self, *_: object) -> dict[str, str]:
        return {"id": str(self.user_id)}

    def list_owned_wardrobe_items(self, **_: object) -> list[WardrobeItemSummary]:
        return [
            WardrobeItemSummary(
                item_id=self.item_id,
                label="Blue shirt",
                created_at=datetime(2026, 10, 17, tzinfo=UTC),
            )
        ]

    def get_owned_wardrobe_item(self, **kwargs: object) -> WardrobeItemRecord | None:
        if kwargs["item_id"] != self.item_id:
            return None
        return WardrobeItemRecord(
            item_id=self.item_id,
            user_id=self.user_id,
            source_features_id=self.feature_id,
            storage_path=f"users/{self.user_id}/items/{self.item_id}/original.jpg",
            mime_type="image/jpeg",
            created_at=datetime(2026, 10, 17, tzinfo=UTC),
            features=make_features(),
            corrected_fields=[CorrectionField.ITEM_NAME],
            active_correction_id=self.previous_correction_id,
        )

    def activate_item_feature_correction(self, **kwargs: object) -> dict[str, str]:
        self.activated = kwargs
        return {"id": str(kwargs["correction_id"])}

    def restore_item_feature_correction(self, **kwargs: object) -> None:
        self.restored = kwargs


class FakeStorage:
    def download(self, path: str) -> bytes:
        assert path.endswith("original.jpg")
        return b"jpeg"


class FakeEmbeddingProvider:
    async def embed(self, canonical_text: str) -> SemanticEmbedding:
        assert "item_type: overshirt" in canonical_text
        return SemanticEmbedding(
            provider="gateway",
            model="embedding-model",
            dimensions=2,
            schema_version=1,
            values=[1.0, 0.0],
        )


class FakeProfileService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def rebuild_if_ready(self, user_id):
        if self.fail:
            raise RuntimeError("profile failed")
        return ProfileRebuildResult(status="READY", usable_item_count=6)


def make_service(
    repository: FakeRepository,
    *,
    profile_service: FakeProfileService | None = None,
) -> WardrobeService:
    return WardrobeService(
        repository=repository,
        storage=FakeStorage(),
        embedding_provider=FakeEmbeddingProvider(),
        profile_service=profile_service or FakeProfileService(),
        pipeline=PIPELINE,
    )


def test_wardrobe_lists_details_and_private_image() -> None:
    repository = FakeRepository()
    service = make_service(repository)

    page = service.list_items(
        telegram_user_id=123,
        display_name="Vinz",
    )
    detail = service.get_item(
        telegram_user_id=123,
        display_name="Vinz",
        item_id=repository.item_id,
    )
    image = service.get_image(
        telegram_user_id=123,
        display_name="Vinz",
        item_id=repository.item_id,
    )

    assert page.items[0].label == "Blue shirt"
    assert detail.corrected_fields == [CorrectionField.ITEM_NAME]
    assert image.data == b"jpeg"
    assert image.mime_type == "image/jpeg"


def test_guided_preview_validates_colours_and_controlled_traits() -> None:
    repository = FakeRepository()
    service = make_service(repository)

    preview = service.preview_correction(
        telegram_user_id=123,
        display_name="Vinz",
        item_id=repository.item_id,
        field=CorrectionField.COLOURS,
        values=["navy", "off white"],
    )

    assert [colour.name for colour in preview.features.colours] == ["navy", "ivory"]
    assert [colour.hex for colour in preview.features.colours] == ["#000080", "#FFFFF0"]
    assert [colour.proportion for colour in preview.features.colours] == [0.5, 0.5]
    materials = service.preview_correction(
        telegram_user_id=123,
        display_name="Vinz",
        item_id=repository.item_id,
        field=CorrectionField.MATERIALS,
        values=["linen", "fake leather"],
    )
    assert [material.value for material in materials.features.materials] == [
        "linen",
        "faux_leather",
    ]
    with pytest.raises(InvalidCorrection, match="Try: Minimal"):
        service.preview_correction(
            telegram_user_id=123,
            display_name="Vinz",
            item_id=repository.item_id,
            field=CorrectionField.STYLE_TRAITS,
            values=["minmal"],
        )


def test_item_type_correction_normalizes_common_terms() -> None:
    repository = FakeRepository()
    preview = make_service(repository).preview_correction(
        telegram_user_id=123,
        display_name="Vinz",
        item_id=repository.item_id,
        field=CorrectionField.ITEM_TYPE,
        values=["tee"],
    )

    assert preview.features.item_type.value == "t-shirt"


def test_confirmed_correction_embeds_persists_and_rebuilds_profile() -> None:
    repository = FakeRepository()
    service = make_service(repository)

    result = run(
        service.apply_correction(
            telegram_user_id=123,
            display_name="Vinz",
            item_id=repository.item_id,
            field=CorrectionField.ITEM_TYPE,
            values=["overshirt"],
        )
    )

    assert result.features.item_type.value == "overshirt"
    assert result.profile.status == "READY"
    assert repository.activated is not None
    assert repository.activated["source_features_id"] == repository.feature_id
    assert repository.activated["corrected_fields"] == [
        CorrectionField.ITEM_NAME,
        CorrectionField.ITEM_TYPE,
    ]


def test_profile_failure_restores_previous_correction() -> None:
    repository = FakeRepository()
    service = make_service(repository, profile_service=FakeProfileService(fail=True))

    with pytest.raises(WardrobePersistenceError):
        run(
            service.apply_correction(
                telegram_user_id=123,
                display_name="Vinz",
                item_id=repository.item_id,
                field=CorrectionField.ITEM_TYPE,
                values=["overshirt"],
            )
        )

    assert repository.restored is not None
    assert repository.restored["previous_correction_id"] == repository.previous_correction_id
