from uuid import uuid4

import pytest

from aura_backend.application.matching import ActiveProfile
from aura_backend.application.profiles import ProfilePersistenceError, ProfileReadService
from aura_backend.domain.models import AestheticProfileV1, SemanticEmbedding
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
    def __init__(self, *, item_count: int, active_profile: ActiveProfile | None) -> None:
        self.user_id = uuid4()
        self.item_count = item_count
        self.active_profile = active_profile

    def find_or_create_user(self, _: int, display_name: str | None):
        return {"id": str(self.user_id), "display_name": display_name}

    def list_profile_inputs(self, **_: object):
        return [object() for _ in range(self.item_count)]

    def get_active_profile(self, **_: object):
        return self.active_profile


def make_active_profile(user_id) -> ActiveProfile:
    profile = AestheticProfileV1(
        user_id=user_id,
        colours=[
            {"name": "cream", "hex": "#FFFDD0", "weight": 0.5},
            {"name": "black", "hex": "#000000", "weight": 0.3},
            {"name": "beige", "hex": "#F5F5DC", "weight": 0.2},
        ],
        patterns=[{"value": "plain", "weight": 1.0}],
        materials=[{"value": "cotton", "weight": 1.0}],
        shape_traits=[{"value": "clean_lined", "weight": 1.0}],
        decorative_details=[{"value": "minimal_detail", "weight": 1.0}],
        style_traits=[
            {"value": "minimal", "weight": 0.5},
            {"value": "casual", "weight": 0.3},
            {"value": "classic", "weight": 0.2},
        ],
        aesthetic_signals=[{"value": "quiet_luxury", "weight": 1.0}],
        embedding_centroid=SemanticEmbedding(
            provider="gateway",
            model="embedding-model",
            dimensions=2,
            schema_version=1,
            values=[0.6, 0.8],
        ),
        colour_diversity=0.5,
        style_diversity=0.5,
        contributing_feature_ids=[uuid4() for _ in range(5)],
        summary="Based on your uploaded belongings, your profile leans toward cream.",
        algorithm_version=1,
    )
    return ActiveProfile(profile_id=uuid4(), profile=profile)


def test_profile_read_reports_collecting_progress() -> None:
    repository = FakeRepository(item_count=3, active_profile=None)
    service = ProfileReadService(repository=repository, pipeline=PIPELINE)  # type: ignore[arg-type]

    result = service.get(telegram_user_id=123, display_name="Vinz")

    assert result.status == "COLLECTING"
    assert result.display_name == "Vinz"
    assert result.usable_item_count == 3
    assert result.minimum_item_count == 5
    assert result.profile is None


def test_profile_read_reports_unavailable_when_enough_items_have_no_profile() -> None:
    repository = FakeRepository(item_count=5, active_profile=None)
    service = ProfileReadService(repository=repository, pipeline=PIPELINE)  # type: ignore[arg-type]

    result = service.get(telegram_user_id=123, display_name="Vinz")

    assert result.status == "UNAVAILABLE"


def test_profile_read_returns_only_display_safe_top_values() -> None:
    repository = FakeRepository(item_count=5, active_profile=None)
    repository.active_profile = make_active_profile(repository.user_id)
    service = ProfileReadService(repository=repository, pipeline=PIPELINE)  # type: ignore[arg-type]

    result = service.get(telegram_user_id=123, display_name="Vinz")

    assert result.status == "READY"
    assert result.profile is not None
    assert result.profile.colours == ["cream", "black", "beige"]
    assert result.profile.style_traits == ["minimal", "casual", "classic"]
    assert result.profile.shape_traits == ["clean lined"]
    assert result.profile.style_influences == ["quiet luxury"]
    assert "Cream is your strongest palette anchor" in result.profile.summary
    assert "minimal and casual are your clearest style traits" in result.profile.summary
    assert "cotton materials" in result.profile.summary
    assert "clean lined shapes" in result.profile.summary
    assert "quiet luxury as the strongest style influence" in result.profile.summary
    assert "black" not in result.profile.summary.lower()


def test_profile_read_wraps_repository_failures() -> None:
    repository = FakeRepository(item_count=0, active_profile=None)

    def fail(**_: object):
        raise RuntimeError("database unavailable")

    repository.list_profile_inputs = fail  # type: ignore[method-assign]
    service = ProfileReadService(repository=repository, pipeline=PIPELINE)  # type: ignore[arg-type]

    with pytest.raises(ProfilePersistenceError):
        service.get(telegram_user_id=123, display_name="Vinz")
