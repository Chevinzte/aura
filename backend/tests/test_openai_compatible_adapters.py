from __future__ import annotations

import json
from asyncio import run

import httpx
import pytest

from aura_backend.ai.contracts import ImageInput
from aura_backend.ai.openai_compatible import (
    EmbeddingResponseError,
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleVisionAnalyzer,
)
from aura_backend.domain.models import (
    ColourObservation,
    ImageQuality,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
)


def make_features_payload() -> dict[str, object]:
    features = ItemVisualFeaturesV1(
        item_type=ItemTypeObservation(value="handbag", confidence=0.95),
        item_name="blush pink handbag",
        colours=[
            ColourObservation(
                name="blush pink",
                hex="#D9A6AA",
                proportion=1.0,
                confidence=0.9,
            )
        ],
        quality=ImageQuality(usable=True, score=0.95),
        description="A blush pink handbag.",
    )
    return features.model_dump(by_alias=True, mode="json")


def test_vision_adapter_sends_image_and_validates_json_response() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(make_features_payload())}}
                ]
            },
        )

    analyzer = OpenAICompatibleVisionAnalyzer(
        base_url="https://gateway.example/v1",
        api_key="test-key",
        model="gemini-3.5-flash-lite",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )

    result = run(analyzer.analyze(ImageInput(data=b"image-bytes", mime_type="image/png")))

    assert result.item_type.value == "handbag"
    request_payload = json.loads(requests[0].content)
    assert request_payload["response_format"] == {"type": "json_object"}
    assert request_payload["messages"][1]["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )


def test_vision_adapter_moves_style_value_out_of_shape_traits() -> None:
    payload = make_features_payload()
    payload["shapeTraits"] = [{"value": "classic", "confidence": 0.9}]
    payload["styleTraits"] = []

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    analyzer = OpenAICompatibleVisionAnalyzer(
        base_url="https://gateway.example/v1",
        api_key="test-key",
        model="gemini-3.5-flash-lite",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )

    result = run(analyzer.analyze(ImageInput(data=b"image-bytes", mime_type="image/png")))

    assert result.shape_traits == []
    assert [trait.value for trait in result.style_traits] == ["classic"]


def test_vision_adapter_routes_controlled_values_to_their_schema_field() -> None:
    payload = make_features_payload()
    payload["patterns"] = []
    payload["textures"] = [{"value": "textured", "confidence": 0.8}]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    analyzer = OpenAICompatibleVisionAnalyzer(
        base_url="https://gateway.example/v1",
        api_key="test-key",
        model="gemini-3.5-flash-lite",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )

    result = run(analyzer.analyze(ImageInput(data=b"image-bytes", mime_type="image/png")))

    assert [pattern.value for pattern in result.patterns] == ["textured"]
    assert result.textures == []


def test_vision_adapter_preserves_unknown_vocabulary_in_observations() -> None:
    payload = make_features_payload()
    payload["materials"] = [{"value": "satin", "confidence": 0.8}]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    analyzer = OpenAICompatibleVisionAnalyzer(
        base_url="https://gateway.example/v1",
        api_key="test-key",
        model="gemini-3.5-flash-lite",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )

    result = run(analyzer.analyze(ImageInput(data=b"image-bytes", mime_type="image/png")))

    assert result.materials == []
    assert "Unmapped materials value: satin" in result.observations


def test_embedding_adapter_returns_configured_dimension_vector() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.2, 0.8]}]})

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://gateway.example/v1",
        api_key="test-key",
        model="text-embedding-3-small",
        dimensions=2,
        schema_version=1,
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )

    embedding = run(provider.embed("item_type: handbag"))

    assert embedding.model == "text-embedding-3-small"
    assert embedding.values == [0.2, 0.8]


def test_embedding_adapter_rejects_unexpected_dimensions() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.2]}]})

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://gateway.example/v1",
        api_key="test-key",
        model="text-embedding-3-small",
        dimensions=2,
        schema_version=1,
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingResponseError, match="dimension"):
        run(provider.embed("item_type: handbag"))
