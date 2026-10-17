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


def test_profile_management_requests_use_expected_endpoints() -> None:
    item_id = uuid4()
    seen: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers["X-Telegram-User-Id"] == "123"
        if request.method == "GET":
            assert request.url.params["page"] == "1"
            return httpx.Response(
                200,
                json={
                    "items": [],
                    "page": 1,
                    "page_size": 10,
                    "has_previous": False,
                    "has_next": False,
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "COLLECTING",
                "usable_item_count": 0,
                "removed_item_count": 1,
            },
        )

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )
    run(client.list_profile_items(telegram_user_id=123, display_name="Vinz"))
    run(
        client.remove_profile_item(
            telegram_user_id=123,
            display_name="Vinz",
            item_id=item_id,
        )
    )
    run(client.reset_profile(telegram_user_id=123, display_name="Vinz"))
    run(client.close())

    assert seen == [
        ("GET", "/v1/profile/items"),
        ("DELETE", f"/v1/profile/items/{item_id}"),
        ("DELETE", "/v1/profile"),
    ]


def test_suggestion_request_uses_backend_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/suggestions"
        assert request.headers["X-Telegram-User-Id"] == "123"
        body = await request.aread()
        assert b'"intent":"SAFE_EXTENSION"' in body
        assert b'"category":"TOPS"' in body
        assert b'"count":3' in body
        return httpx.Response(200, json={"suggestions": []})

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )
    result = run(
        client.generate_suggestions(
            telegram_user_id=123,
            display_name="Vinz",
            intent="SAFE_EXTENSION",
            category="TOPS",
            count=3,
            exclude_labels=[],
        )
    )
    run(client.close())

    assert result == {"suggestions": []}


def test_preference_requests_use_backend_contract() -> None:
    seen: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers["X-Telegram-User-Id"] == "123"
        if request.method == "PUT":
            assert b'"fashion_presentation":"MENSWEAR"' in await request.aread()
            return httpx.Response(200, json={"fashion_presentation": "MENSWEAR"})
        return httpx.Response(200, json={"fashion_presentation": None})

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )
    initial = run(client.get_preferences(telegram_user_id=123, display_name="Vinz"))
    updated = run(
        client.update_fashion_presentation(
            telegram_user_id=123,
            display_name="Vinz",
            fashion_presentation="MENSWEAR",
        )
    )
    run(client.close())

    assert initial == {"fashion_presentation": None}
    assert updated == {"fashion_presentation": "MENSWEAR"}
    assert seen == [
        ("GET", "/v1/preferences"),
        ("PUT", "/v1/preferences/fashion-presentation"),
    ]


def test_wardrobe_requests_use_backend_contract() -> None:
    item_id = uuid4()
    seen: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers["X-Telegram-User-Id"] == "123"
        if request.url.path.endswith("/image"):
            return httpx.Response(200, content=b"jpeg", headers={"Content-Type": "image/jpeg"})
        if request.url.path.endswith("/correction-options"):
            return httpx.Response(200, json=[{"field": "item_name"}])
        if request.url.path.endswith("/corrections/preview"):
            return httpx.Response(200, json={"field": "item_name", "features": {}})
        if request.url.path.endswith("/corrections"):
            return httpx.Response(200, json={"profile_status": "READY"})
        if request.url.path == f"/v1/wardrobe/items/{item_id}":
            return httpx.Response(200, json={"item_id": str(item_id)})
        return httpx.Response(200, json={"items": [], "page": 1})

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )
    run(client.list_wardrobe_items(telegram_user_id=123, display_name="Vinz"))
    run(
        client.get_wardrobe_item(
            telegram_user_id=123,
            display_name="Vinz",
            item_id=item_id,
        )
    )
    image, mime_type = run(
        client.get_wardrobe_item_image(
            telegram_user_id=123,
            display_name="Vinz",
            item_id=item_id,
        )
    )
    options = run(client.get_correction_options(telegram_user_id=123))
    run(
        client.preview_item_correction(
            telegram_user_id=123,
            display_name="Vinz",
            item_id=item_id,
            field="item_name",
            values=["Travel bag"],
        )
    )
    run(
        client.apply_item_correction(
            telegram_user_id=123,
            display_name="Vinz",
            item_id=item_id,
            field="item_name",
            values=["Travel bag"],
        )
    )
    run(client.close())

    assert image == b"jpeg"
    assert mime_type == "image/jpeg"
    assert options == [{"field": "item_name"}]
    assert seen == [
        ("GET", "/v1/wardrobe"),
        ("GET", f"/v1/wardrobe/items/{item_id}"),
        ("GET", f"/v1/wardrobe/items/{item_id}/image"),
        ("GET", "/v1/wardrobe/correction-options"),
        ("POST", f"/v1/wardrobe/items/{item_id}/corrections/preview"),
        ("POST", f"/v1/wardrobe/items/{item_id}/corrections"),
    ]


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
