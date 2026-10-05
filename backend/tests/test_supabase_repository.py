from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from aura_backend.domain.models import (
    ColourObservation,
    ImageQuality,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    SemanticEmbedding,
)
from aura_backend.repositories.supabase import AuraRepository, FeaturePipelineVersion


class FakeTable:
    def __init__(self, response_data: list[dict[str, object]]) -> None:
        self.response_data = response_data
        self.operation: str | None = None
        self.payload: dict[str, object] | None = None
        self.filters: list[tuple[str, str]] = []

    def insert(self, payload: dict[str, object]) -> FakeTable:
        self.operation = "insert"
        self.payload = payload
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

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.response_data)


class FakeSupabaseClient:
    def __init__(self) -> None:
        self.tables: dict[str, FakeTable] = {}
        self.rpc_calls: list[tuple[str, dict[str, object]]] = []

    def table(self, name: str) -> FakeTable:
        return self.tables.setdefault(name, FakeTable([{"id": str(uuid4())}]))

    def rpc(self, name: str, params: dict[str, object]) -> FakeTable:
        self.rpc_calls.append((name, params))
        return FakeTable([{"id": str(uuid4())}])


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
