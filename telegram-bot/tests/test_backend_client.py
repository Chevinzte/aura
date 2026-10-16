from asyncio import run
from uuid import uuid4

import httpx
import pytest

from aura_telegram.backend import AuraBackendClient, BackendAPIError


def test_owned_upload_sends_identity_and_multipart_image() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/items/owned"
        assert request.headers["X-Telegram-User-Id"] == "123"
        assert request.headers["X-Telegram-Display-Name"] == "AURA User"
        assert request.headers["Content-Type"].startswith("multipart/form-data")
        return httpx.Response(201, json={"status": "READY"})

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )
    result = run(
        client.upload_owned_item(
            telegram_user_id=123,
            display_name="AURA User",
            image=b"jpeg",
            filename="item.jpg",
            item_name="Bag",
        )
    )
    run(client.close())

    assert result["status"] == "READY"


def test_feedback_uses_match_endpoint_and_stable_type() -> None:
    match_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/v1/matches/{match_id}/feedback"
        assert request.headers["X-Telegram-User-Id"] == "123"
        assert b'"feedback_type":"LIKE"' in await request.aread()
        return httpx.Response(200, json={"feedback_type": "LIKE"})

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )
    result = run(
        client.submit_feedback(
            telegram_user_id=123,
            match_id=match_id,
            feedback_type="LIKE",
        )
    )
    run(client.close())

    assert result["feedback_type"] == "LIKE"


def test_profile_request_sends_identity_headers() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/profile"
        assert request.headers["X-Telegram-User-Id"] == "123"
        assert request.headers["X-Telegram-Display-Name"] == "Vinz"
        return httpx.Response(200, json={"status": "COLLECTING"})

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )
    result = run(client.get_profile(telegram_user_id=123, display_name="Vinz"))
    run(client.close())

    assert result["status"] == "COLLECTING"


def test_backend_error_detail_is_preserved() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "PROFILE_NOT_READY"})

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(BackendAPIError, match="PROFILE_NOT_READY") as error:
        run(
            client.upload_candidate_item(
                telegram_user_id=123,
                display_name=None,
                image=b"jpeg",
                filename="candidate.jpg",
                item_name=None,
            )
        )
    run(client.close())

    assert error.value.status_code == 409
