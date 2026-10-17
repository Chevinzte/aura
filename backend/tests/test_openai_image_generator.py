from asyncio import run
import base64
import json

import httpx
import pytest

from aura_backend.ai.contracts import ImageGenerationError
from aura_backend.ai.openai_images import OpenAIImageGenerator


def test_openai_image_generator_returns_decoded_jpeg() -> None:
    image_bytes = b"generated-jpeg"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/images/generations"
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(await request.aread())
        assert payload["model"] == "gpt-image-test"
        assert payload["quality"] == "low"
        assert payload["size"] == "1024x1024"
        assert payload["output_format"] == "jpeg"
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(image_bytes).decode()}]},
        )

    generator = OpenAIImageGenerator(
        base_url="https://api.openai.test/v1",
        api_key="test-key",
        model="gpt-image-test",
        timeout_seconds=10,
        quality="low",
        size="1024x1024",
        transport=httpx.MockTransport(handler),
    )

    image = run(generator.generate("One isolated jacket"))

    assert image.data == image_bytes
    assert image.mime_type == "image/jpeg"


def test_openai_image_generator_requires_configuration() -> None:
    generator = OpenAIImageGenerator(
        base_url="https://api.openai.test/v1",
        api_key=None,
        model="gpt-image-test",
        timeout_seconds=10,
        quality="low",
        size="1024x1024",
    )

    with pytest.raises(ImageGenerationError, match="not configured"):
        run(generator.generate("One isolated jacket"))


def test_openai_image_generator_rejects_missing_image_data() -> None:
    generator = OpenAIImageGenerator(
        base_url="https://api.openai.test/v1",
        api_key="test-key",
        model="gpt-image-test",
        timeout_seconds=10,
        quality="low",
        size="1024x1024",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": []})),
    )

    with pytest.raises(ImageGenerationError, match="no generated image"):
        run(generator.generate("One isolated jacket"))
