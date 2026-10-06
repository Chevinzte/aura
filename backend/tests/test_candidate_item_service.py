from asyncio import run
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image

from aura_backend.application.candidate_items import CandidateItemService, ProfileNotReady
from aura_backend.application.matching import ActiveProfile, CandidateMatcher
from aura_backend.domain.models import (
    AestheticProfileV1,
    ColourObservation,
    ImageQuality,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    SemanticEmbedding,
)
from aura_backend.media.images import ImageValidator
from aura_backend.repositories.supabase import FeaturePipelineVersion


def make_embedding(values: list[float]) -> SemanticEmbedding:
    return SemanticEmbedding(
        provider="test",
        model="embedding-v1",
        dimensions=2,
        schema_version=1,
        values=values,
    )


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


def make_profile(user_id) -> ActiveProfile:
    return ActiveProfile(
        profile_id=uuid4(),
        profile=AestheticProfileV1(
            user_id=user_id,
            colours=[{"name": "pink", "hex": "#FFC0CB", "weight": 1.0}],
            embedding_centroid=make_embedding([1.0, 0.0]),
            colour_diversity=0,
            style_diversity=0,
            contributing_feature_ids=[uuid4() for _ in range(5)],
            summary="A pink profile.",
            algorithm_version=1,
        ),
    )


class FakeRepository:
    def __init__(self, *, profile_ready: bool = True) -> None:
        self.user_id = uuid4()
        self.analysis_id = uuid4()
        self.profile_ready = profile_ready
        self.create_args = None
        self.saved_match = None

    def find_or_create_user(self, telegram_user_id: int, display_name: str | None):
        return {"id": str(self.user_id)}

    def get_active_profile(self, **_: object):
        return make_profile(self.user_id) if self.profile_ready else None

    def create_item_with_analysis(self, **kwargs: object):
        self.create_args = kwargs
        return {"analysis_id": str(self.analysis_id)}

    def save_match_analysis(self, **kwargs: object):
        self.saved_match = kwargs
        return {"id": str(uuid4())}


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded = False

    def upload(self, **_: object) -> None:
        self.uploaded = True

    def delete(self, path: str) -> None:
        pass


class FakeAnalysisService:
    async def analyze(self, *, analysis_id, image):
        return SimpleNamespace(
            analysis_id=analysis_id,
            features=make_features(),
            embedding=make_embedding([1.0, 0.0]),
        )


def make_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (300, 300), "pink").save(output, format="PNG")
    return output.getvalue()


def make_service(repository: FakeRepository, storage: FakeStorage) -> CandidateItemService:
    return CandidateItemService(
        repository=repository,
        storage=storage,
        image_validator=ImageValidator(max_bytes=1_000_000, min_dimension=256),
        item_analysis=FakeAnalysisService(),  # type: ignore[arg-type]
        matcher=CandidateMatcher(),
        pipeline=FeaturePipelineVersion(
            vision_provider="test",
            vision_model="vision-v1",
            vision_prompt_version=1,
            feature_schema_version=1,
            embedding_provider="test",
            embedding_model="embedding-v1",
            embedding_dimensions=2,
            embedding_schema_version=1,
        ),
    )


def test_candidate_is_analyzed_matched_and_persisted() -> None:
    repository = FakeRepository()
    storage = FakeStorage()

    result = run(
        make_service(repository, storage).create_and_match(
            telegram_user_id=123,
            display_name="AURA User",
            filename="candidate.png",
            declared_mime_type="image/png",
            data=make_png(),
            item_name="Candidate bag",
        )
    )

    assert storage.uploaded is True
    assert repository.create_args["source"] == "CANDIDATE"
    assert repository.saved_match is not None
    assert result.match.classification == "STRONG_FIT"


def test_candidate_requires_profile_before_uploading() -> None:
    repository = FakeRepository(profile_ready=False)
    storage = FakeStorage()

    with pytest.raises(ProfileNotReady):
        run(
            make_service(repository, storage).create_and_match(
                telegram_user_id=123,
                display_name=None,
                filename="candidate.png",
                declared_mime_type="image/png",
                data=make_png(),
                item_name=None,
            )
        )

    assert storage.uploaded is False
