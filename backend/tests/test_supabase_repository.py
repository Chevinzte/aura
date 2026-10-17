from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from aura_backend.domain.models import (
    AestheticProfileV1,
    FeedbackCategory,
    FeedbackType,
    ColourObservation,
    ImageQuality,
    ItemSource,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    MatchComponentScore,
    MatchDimension,
    MatchResultV1,
    SemanticEmbedding,
)
from aura_backend.application.preferences import FashionPresentation
from aura_backend.repositories.supabase import AuraRepository, FeaturePipelineVersion


class FakeTable:
    def __init__(self, response_data: object) -> None:
        self.response_data = response_data
        self.operation: str | None = None
        self.payload: dict[str, object] | None = None
        self.filters: list[tuple[str, str]] = []
        self.requested_range: tuple[int, int] | None = None

    def insert(self, payload: dict[str, object]) -> FakeTable:
        self.operation = "insert"
        self.payload = payload
        return self

    def select(self, _: str) -> FakeTable:
        self.operation = "select"
        return self

    def update(self, payload: dict[str, object]) -> FakeTable:
        self.operation = "update"
        self.payload = payload
        return self

    def upsert(self, payload: dict[str, object], **_: object) -> FakeTable:
        self.operation = "upsert"
        self.payload = payload
        return self

    def eq(self, column: str, value: str) -> FakeTable:
        self.filters.append((column, value))
        return self

    def is_(self, column: str, value: str) -> FakeTable:
        self.filters.append((column, value))
        return self

    def order(self, _: str, **__: object) -> FakeTable:
        return self

    def limit(self, _: int) -> FakeTable:
        return self

    def range(self, start: int, end: int) -> FakeTable:
        self.requested_range = (start, end)
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.response_data)


class FakeSupabaseClient:
    def __init__(self) -> None:
        self.tables: dict[str, FakeTable] = {}
        self.rpc_calls: list[tuple[str, dict[str, object]]] = []
        self.rpc_response_data: object = [{"id": str(uuid4())}]

    def table(self, name: str) -> FakeTable:
        return self.tables.setdefault(name, FakeTable([{"id": str(uuid4())}]))

    def rpc(self, name: str, params: dict[str, object]) -> FakeTable:
        self.rpc_calls.append((name, params))
        return FakeTable(self.rpc_response_data)


def make_features() -> ItemVisualFeaturesV1:
    return ItemVisualFeaturesV1(
        item_type=ItemTypeObservation(value="handbag", confidence=0.98),
        item_name="floral handbag",
        colours=[
            ColourObservation(
                name="blush pink",
                hex="#D9A6AA",
                proportion=1.0,
                confidence=0.91,
            )
        ],
        quality=ImageQuality(usable=True, score=0.9),
        description="A blush pink handbag.",
    )


def test_pending_feature_analysis_persists_pipeline_versions() -> None:
    client = FakeSupabaseClient()
    repository = AuraRepository(client)  # type: ignore[arg-type]
    item_id = uuid4()

    repository.create_pending_feature_analysis(
        item_id=item_id,
        pipeline=FeaturePipelineVersion(
            vision_provider="gateway",
            vision_model="gemini-3.5-flash-lite",
            vision_prompt_version=1,
            feature_schema_version=1,
            embedding_provider="gateway",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=1536,
            embedding_schema_version=1,
        ),
    )

    table = client.tables["item_visual_features"]
    assert table.operation == "insert"
    assert table.payload is not None
    assert table.payload["item_id"] == str(item_id)
    assert table.payload["embedding_dimensions"] == 1536


def test_update_user_fashion_presentation_updates_owned_user() -> None:
    client = FakeSupabaseClient()
    user_id = uuid4()
    client.tables["users"] = FakeTable(
        [{"id": str(user_id), "fashion_presentation": "MENSWEAR"}]
    )
    repository = AuraRepository(client)  # type: ignore[arg-type]

    updated = repository.update_user_fashion_presentation(
        user_id=user_id,
        fashion_presentation=FashionPresentation.MENSWEAR,
    )

    table = client.tables["users"]
    assert table.payload == {"fashion_presentation": "MENSWEAR"}
    assert ("id", str(user_id)) in table.filters
    assert updated["fashion_presentation"] == "MENSWEAR"


def test_create_item_with_analysis_uses_atomic_rpc() -> None:
    client = FakeSupabaseClient()
    repository = AuraRepository(client)  # type: ignore[arg-type]
    item_id = uuid4()
    user_id = uuid4()

    repository.create_item_with_analysis(
        item_id=item_id,
        user_id=user_id,
        source=ItemSource.OWNED,
        storage_path=f"users/{user_id}/items/{item_id}/original.png",
        original_filename="bag.png",
        mime_type="image/png",
        size_bytes=100,
        width_px=300,
        height_px=300,
        content_sha256="a" * 64,
        item_name="Bag",
        pipeline=FeaturePipelineVersion(
            vision_provider="gateway",
            vision_model="vision-model",
            vision_prompt_version=1,
            feature_schema_version=1,
            embedding_provider="gateway",
            embedding_model="embedding-model",
            embedding_dimensions=1536,
            embedding_schema_version=1,
        ),
    )

    function_name, params = client.rpc_calls[0]
    assert function_name == "create_item_with_analysis"
    assert params["p_item_id"] == str(item_id)
    assert params["p_source"] == "OWNED"


def test_complete_feature_analysis_persists_validated_json_and_vector() -> None:
    client = FakeSupabaseClient()
    repository = AuraRepository(client)  # type: ignore[arg-type]
    analysis_id = uuid4()
    embedding = SemanticEmbedding(
        provider="gateway",
        model="text-embedding-3-small",
        dimensions=2,
        schema_version=1,
        values=[0.3, 0.4],
    )

    repository.complete_feature_analysis(
        analysis_id=analysis_id,
        features=make_features(),
        canonical_embedding_text="item_type: handbag\ncolours: blush pink",
        embedding=embedding,
    )

    function_name, params = client.rpc_calls[0]
    assert function_name == "complete_item_feature_analysis"
    assert params["p_analysis_id"] == str(analysis_id)
    assert params["p_features"]["itemType"]["value"] == "handbag"
    assert params["p_embedding"] == [0.3, 0.4]


def test_lifecycle_rpc_accepts_composite_object_response() -> None:
    client = FakeSupabaseClient()
    analysis_id = uuid4()
    client.rpc_response_data = {"id": str(analysis_id), "status": "PROCESSING"}
    repository = AuraRepository(client)  # type: ignore[arg-type]

    result = repository.mark_feature_analysis_processing(analysis_id)

    assert result["id"] == str(analysis_id)
    assert result["status"] == "PROCESSING"


def test_list_profile_inputs_parses_pgvector_and_validated_features() -> None:
    client = FakeSupabaseClient()
    feature_id = uuid4()
    client.tables["item_visual_features"] = FakeTable(
        [
            {
                "id": str(feature_id),
                "features": make_features().model_dump(by_alias=True, mode="json"),
                "embedding": "[0.3,0.4]",
                "embedding_provider": "gateway",
                "embedding_model": "embedding-model",
                "embedding_dimensions": 2,
                "embedding_schema_version": 1,
                "items": {"content_sha256": "a" * 64},
            }
        ]
    )
    repository = AuraRepository(client)  # type: ignore[arg-type]

    inputs = repository.list_profile_inputs(
        user_id=uuid4(),
        pipeline=FeaturePipelineVersion(
            vision_provider="gateway",
            vision_model="vision-model",
            vision_prompt_version=1,
            feature_schema_version=1,
            embedding_provider="gateway",
            embedding_model="embedding-model",
            embedding_dimensions=2,
            embedding_schema_version=1,
        ),
    )

    assert inputs[0].feature_id == feature_id
    assert inputs[0].embedding.values == [0.3, 0.4]


def test_activate_profile_uses_atomic_rpc() -> None:
    client = FakeSupabaseClient()
    repository = AuraRepository(client)  # type: ignore[arg-type]
    user_id = uuid4()
    feature_ids = [uuid4() for _ in range(5)]
    profile = AestheticProfileV1(
        user_id=user_id,
        colours=[{"name": "pink", "hex": "#FFC0CB", "weight": 1.0}],
        embedding_centroid=SemanticEmbedding(
            provider="gateway",
            model="embedding-model",
            dimensions=2,
            schema_version=1,
            values=[0.6, 0.8],
        ),
        colour_diversity=0,
        style_diversity=0,
        contributing_feature_ids=feature_ids,
        summary="A pink profile.",
        algorithm_version=1,
    )

    repository.activate_profile(
        profile_id=uuid4(),
        profile=profile,
        effective_weights={feature_id: 0.2 for feature_id in feature_ids},
        pipeline=FeaturePipelineVersion(
            vision_provider="gateway",
            vision_model="vision-model",
            vision_prompt_version=1,
            feature_schema_version=1,
            embedding_provider="gateway",
            embedding_model="embedding-model",
            embedding_dimensions=2,
            embedding_schema_version=1,
        ),
    )

    function_name, params = client.rpc_calls[0]
    assert function_name == "activate_aesthetic_profile"
    assert len(params["p_contributions"]) == 5


def test_get_active_profile_validates_stored_profile_data() -> None:
    client = FakeSupabaseClient()
    user_id = uuid4()
    profile_id = uuid4()
    feature_ids = [uuid4() for _ in range(5)]
    profile = AestheticProfileV1(
        user_id=user_id,
        colours=[{"name": "pink", "hex": "#FFC0CB", "weight": 1.0}],
        embedding_centroid=SemanticEmbedding(
            provider="gateway",
            model="embedding-model",
            dimensions=2,
            schema_version=1,
            values=[0.6, 0.8],
        ),
        colour_diversity=0,
        style_diversity=0,
        contributing_feature_ids=feature_ids,
        summary="A pink profile.",
        algorithm_version=1,
    )
    client.tables["aesthetic_profiles"] = FakeTable(
        [
            {
                "id": str(profile_id),
                "profile_data": profile.model_dump(by_alias=True, mode="json"),
            }
        ]
    )
    repository = AuraRepository(client)  # type: ignore[arg-type]

    active = repository.get_active_profile(
        user_id=user_id,
        pipeline=FeaturePipelineVersion(
            vision_provider="gateway",
            vision_model="vision-model",
            vision_prompt_version=1,
            feature_schema_version=1,
            embedding_provider="gateway",
            embedding_model="embedding-model",
            embedding_dimensions=2,
            embedding_schema_version=1,
        ),
    )

    assert active.profile_id == profile_id
    assert active.profile.user_id == user_id


def test_list_owned_profile_items_uses_caption_or_analyzed_name() -> None:
    client = FakeSupabaseClient()
    item_id = uuid4()
    client.tables["items"] = FakeTable(
        [
            {
                "id": str(item_id),
                "item_name": None,
                "created_at": "2026-10-16T04:00:00Z",
                "item_visual_features": [
                    {
                        "features": make_features().model_dump(
                            by_alias=True,
                            mode="json",
                        )
                    }
                ],
            }
        ]
    )
    repository = AuraRepository(client)  # type: ignore[arg-type]

    items = repository.list_owned_profile_items(
        user_id=uuid4(),
        pipeline=FeaturePipelineVersion(
            vision_provider="gateway",
            vision_model="vision-model",
            vision_prompt_version=1,
            feature_schema_version=1,
            embedding_provider="gateway",
            embedding_model="embedding-model",
            embedding_dimensions=2,
            embedding_schema_version=1,
        ),
        limit=10,
    )

    assert items[0].item_id == item_id
    assert items[0].label == "floral handbag"
    assert client.tables["items"].requested_range == (0, 9)
    assert items[0].created_at == datetime(2026, 10, 16, 4, tzinfo=UTC)


def test_profile_management_rpcs_return_removed_items() -> None:
    client = FakeSupabaseClient()
    repository = AuraRepository(client)  # type: ignore[arg-type]
    user_id = uuid4()
    item_id = uuid4()
    client.rpc_response_data = [{"item_id": str(item_id)}]

    repository.remove_owned_item(user_id=user_id, item_id=item_id)
    reset_count = repository.reset_owned_items(user_id=user_id)

    assert reset_count == 1
    assert client.rpc_calls[0][0] == "remove_owned_profile_item"
    assert client.rpc_calls[1][0] == "reset_owned_profile_items"


def test_save_match_analysis_uses_idempotent_rpc() -> None:
    client = FakeSupabaseClient()
    repository = AuraRepository(client)  # type: ignore[arg-type]
    candidate_item_id = uuid4()
    profile_id = uuid4()
    match = MatchResultV1(
        candidate_item_id=candidate_item_id,
        profile_id=profile_id,
        overall_score=0.8,
        classification="STRONG_FIT",
        component_scores=[
            MatchComponentScore(
                dimension=MatchDimension.COLOUR,
                score=0.8,
                effective_weight=1.0,
                confidence=0.9,
            )
        ],
        explanation="Strong Fit. Based on your uploaded items.",
        scoring_version=1,
        explanation_version=1,
    )

    repository.save_match_analysis(
        match_id=uuid4(),
        user_id=uuid4(),
        candidate_features_id=uuid4(),
        match=match,
    )

    function_name, params = client.rpc_calls[0]
    assert function_name == "record_completed_match"
    assert params["p_candidate_item_id"] == str(candidate_item_id)
    assert params["p_classification"] == "STRONG_FIT"


def test_feedback_repository_checks_ownership_and_uses_upsert_rpc() -> None:
    client = FakeSupabaseClient()
    user_id = uuid4()
    match_id = uuid4()
    client.tables["users"] = FakeTable([{"id": str(user_id)}])
    client.tables["match_analyses"] = FakeTable([{"id": str(match_id)}])
    repository = AuraRepository(client)  # type: ignore[arg-type]

    assert repository.find_user_by_telegram_id(123)["id"] == str(user_id)
    assert repository.match_belongs_to_user(match_id=match_id, user_id=user_id)
    repository.upsert_feedback(
        user_id=user_id,
        match_id=match_id,
        category=FeedbackCategory.TASTE,
        feedback_type=FeedbackType.LIKE,
        note="Accurate",
    )

    function_name, params = client.rpc_calls[0]
    assert function_name == "upsert_match_feedback"
    assert params["p_category"] == "TASTE"
    assert params["p_feedback_type"] == "LIKE"
