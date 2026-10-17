from asyncio import run
import base64
from types import SimpleNamespace

import httpx

from aura_telegram.backend import AuraBackendClient
from aura_telegram.handlers import (
    OWNED_ALBUMS_KEY,
    OWNED_MODE,
    add_owned,
    browse_wardrobe,
    handle_correction_text,
    handle_preference_action,
    handle_photo,
    handle_profile_action,
    handle_suggestion_action,
    handle_wardrobe_action,
    remove_profile_item,
    show_profile,
    request_suggestions,
    show_settings,
)


class FakeMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []
        self.reply_markups: list[object] = []
        self.reply_parse_modes: list[object] = []

    async def reply_text(self, text: str, **kwargs: object) -> None:
        self.replies.append(text)
        self.reply_markups.append(kwargs.get("reply_markup"))
        self.reply_parse_modes.append(kwargs.get("parse_mode"))


def test_add_owned_explains_photo_requirements() -> None:
    message = FakeMessage()
    update = SimpleNamespace(effective_message=message)
    context = SimpleNamespace(user_data={})

    run(add_owned(update, context))  # type: ignore[arg-type]

    guidance = message.replies[0]
    assert context.user_data["upload_mode"] == OWNED_MODE
    assert "batch of up to ten photos" in guidance
    assert "one primary item in each photo" in guidance
    assert "different item, not another angle" in guidance
    assert "avoid faces and personal details" in guidance
    assert "processes batch photos one at a time" in guidance
    assert "Captions are optional" in guidance


def test_owned_album_groups_and_processes_each_photo(monkeypatch) -> None:
    import aura_telegram.handlers as handlers

    monkeypatch.setattr(handlers, "OWNED_ALBUM_SETTLE_SECONDS", 0)
    requests: list[httpx.Request] = []

    async def backend_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        item_count = len(requests)
        return httpx.Response(
            200,
            json={
                "profile_status": "COLLECTING",
                "usable_item_count": item_count,
                "minimum_item_count": 5,
                "features": {"itemName": f"Inferred item {item_count}"},
            },
        )

    class FakeFile:
        def __init__(self, data: bytes) -> None:
            self.data = data

        async def download_as_bytearray(self) -> bytearray:
            return bytearray(self.data)

    class FakePhoto:
        def __init__(self, file_unique_id: str) -> None:
            self.file_unique_id = file_unique_id

        async def get_file(self) -> FakeFile:
            return FakeFile(self.file_unique_id.encode())

    class FakeProgress:
        def __init__(self) -> None:
            self.edits: list[str] = []

        async def edit_text(self, text: str, **_: object) -> None:
            self.edits.append(text)

    class FakeAlbumMessage:
        def __init__(self, photo_id: str, progress: FakeProgress) -> None:
            self.photo = [FakePhoto(photo_id)]
            self.media_group_id = "album-1"
            self.caption = None
            self.progress = progress

        async def reply_text(self, _: str, **__: object) -> FakeProgress:
            return self.progress

    class FakeApplication:
        def __init__(self) -> None:
            self.coroutines = []

        def create_task(self, coroutine, **_: object) -> None:
            self.coroutines.append(coroutine)

    async def scenario() -> None:
        client = AuraBackendClient(
            base_url="http://backend.test",
            timeout_seconds=10,
            transport=httpx.MockTransport(backend_handler),
        )
        progress = FakeProgress()
        application = FakeApplication()
        context = SimpleNamespace(
            user_data={"upload_mode": OWNED_MODE},
            bot_data={"backend_client": client},
            application=application,
        )
        user = SimpleNamespace(id=123, full_name="Vinz")

        for photo_id in ("photo-1", "photo-2"):
            update = SimpleNamespace(
                effective_message=FakeAlbumMessage(photo_id, progress),
                effective_user=user,
            )
            await handle_photo(update, context)  # type: ignore[arg-type]

        album = context.user_data[OWNED_ALBUMS_KEY]["album-1"]
        assert len(album.items) == 2
        application.coroutines[0].close()
        await application.coroutines[1]
        await client.close()

        assert len(requests) == 2
        assert progress.edits[:2] == [
            "Analyzing batch item 1 of 2…",
            "Analyzing batch item 2 of 2…",
        ]
        assert "Batch complete." in progress.edits[-1]
        assert "Added: 2/2" in progress.edits[-1]
        assert "1. Inferred item 1" in progress.edits[-1]
        assert "2. Inferred item 2" in progress.edits[-1]
        assert "Add mode is still active" in progress.edits[-1]
        assert "album-1" not in context.user_data[OWNED_ALBUMS_KEY]

    run(scenario())


def test_show_profile_uses_first_name_and_replies_with_profile() -> None:
    async def backend_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Telegram-Display-Name"] == "Vinz"
        return httpx.Response(
            200,
            json={
                "status": "READY",
                "display_name": "Vinz",
                "usable_item_count": 5,
                "minimum_item_count": 5,
                "profile": {
                    "colours": ["cream"],
                    "style_traits": ["minimal"],
                    "patterns": [],
                    "materials": [],
                    "textures": [],
                    "shape_traits": [],
                    "decorative_details": [],
                    "style_influences": [],
                    "summary": "Your uploaded belongings suggest a minimal profile.",
                },
            },
        )

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    message = FakeMessage()
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=123, first_name="Vinz", username="vinz"),
    )
    context = SimpleNamespace(bot_data={"backend_client": client})

    run(show_profile(update, context))  # type: ignore[arg-type]
    run(client.close())

    assert message.replies[0].startswith("Hello Vinz, this is your style profile")
    assert message.reply_parse_modes[0] == "HTML"


def test_remove_profile_item_lists_owned_item_buttons() -> None:
    item_id = "31a2b686-ffb6-4ab4-a7be-876540bca13a"

    async def backend_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "item_id": item_id,
                        "label": "Favorite bag",
                        "created_at": "2026-10-16T04:00:00Z",
                    }
                ],
                "page": 1,
                "page_size": 10,
                "has_previous": False,
                "has_next": True,
            },
        )

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    message = FakeMessage()
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=123, first_name="Vinz", username="vinz"),
    )
    context = SimpleNamespace(bot_data={"backend_client": client})

    run(remove_profile_item(update, context))  # type: ignore[arg-type]
    run(client.close())

    assert "Choose the belonging" in message.replies[0]
    assert message.reply_markups[0].inline_keyboard[0][0].callback_data == f"rm:{item_id}"
    assert message.reply_markups[0].inline_keyboard[-2][0].callback_data == "rmp:2"


def test_remove_profile_item_can_navigate_to_next_page() -> None:
    item_id = "31a2b686-ffb6-4ab4-a7be-876540bca13a"

    async def backend_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["page"] == "2"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "item_id": item_id,
                        "label": "Older bag",
                        "created_at": "2026-10-01T04:00:00Z",
                    }
                ],
                "page": 2,
                "page_size": 10,
                "has_previous": True,
                "has_next": False,
            },
        )

    class FakeQuery:
        def __init__(self) -> None:
            self.data = "rmp:2"
            self.from_user = SimpleNamespace(id=123, first_name="Vinz", username="vinz")
            self.edits: list[tuple[str, object]] = []

        async def answer(self, *_: object, **__: object) -> None:
            return None

        async def edit_message_text(self, text: str, **kwargs: object) -> None:
            self.edits.append((text, kwargs.get("reply_markup")))

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    query = FakeQuery()
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(bot_data={"backend_client": client})

    run(handle_profile_action(update, context))  # type: ignore[arg-type]
    run(client.close())

    assert "Page 2" in query.edits[0][0]
    keyboard = query.edits[0][1].inline_keyboard
    assert keyboard[0][0].callback_data == f"rm:{item_id}"
    assert keyboard[-2][0].callback_data == "rmp:1"


def test_request_suggestions_displays_intent_choices() -> None:
    async def backend_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/preferences"
        return httpx.Response(200, json={"fashion_presentation": "MENSWEAR"})

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    message = FakeMessage()
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=123, first_name="Vinz", username="vinz"),
    )
    context = SimpleNamespace(
        user_data={},
        bot_data={"backend_client": client},
    )

    run(request_suggestions(update, context))  # type: ignore[arg-type]
    run(client.close())

    keyboard = message.reply_markups[0].inline_keyboard
    assert "Fashion preference: Menswear" in message.replies[0]
    assert keyboard[0][0].callback_data == "sug:SAFE_EXTENSION"
    assert keyboard[1][0].callback_data == "sug:INTENTIONAL_CONTRAST"
    assert keyboard[2][0].callback_data == "sug:SURPRISE_ME"


def test_request_suggestions_prompts_for_unconfigured_preference() -> None:
    async def backend_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"fashion_presentation": None})

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    message = FakeMessage()
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=123, first_name="Vinz", username="vinz"),
    )
    context = SimpleNamespace(
        user_data={},
        bot_data={"backend_client": client},
    )

    run(request_suggestions(update, context))  # type: ignore[arg-type]
    run(client.close())

    keyboard = message.reply_markups[0].inline_keyboard
    assert "Before generating clothing ideas" in message.replies[0]
    assert keyboard[0][0].callback_data == "pref:MENSWEAR:suggestion"
    assert keyboard[1][1].callback_data == "pref:NO_PREFERENCE:suggestion"


def test_settings_updates_preference_and_can_continue_to_suggestions() -> None:
    async def backend_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(200, json={"fashion_presentation": "MENSWEAR"})
        return httpx.Response(200, json={"fashion_presentation": "WOMENSWEAR"})

    class FakeQuery:
        def __init__(self) -> None:
            self.data = "pref:MENSWEAR:suggestion"
            self.from_user = SimpleNamespace(id=123, first_name="Vinz", username="vinz")
            self.edits: list[tuple[str, object]] = []

        async def answer(self, *_: object, **__: object) -> None:
            return None

        async def edit_message_text(self, text: str, **kwargs: object) -> None:
            self.edits.append((text, kwargs.get("reply_markup")))

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    message = FakeMessage()
    user = SimpleNamespace(id=123, first_name="Vinz", username="vinz")
    context = SimpleNamespace(bot_data={"backend_client": client})

    run(
        show_settings(
            SimpleNamespace(effective_message=message, effective_user=user),
            context,
        )
    )  # type: ignore[arg-type]
    query = FakeQuery()
    run(
        handle_preference_action(
            SimpleNamespace(callback_query=query),
            context,
        )
    )  # type: ignore[arg-type]
    run(client.close())

    assert "Fashion preference: Womenswear" in message.replies[0]
    assert "Fashion preference: Menswear" in query.edits[0][0]
    assert query.edits[0][1].inline_keyboard[0][0].callback_data == "sug:SAFE_EXTENSION"


def test_suggestion_action_sends_images_and_offers_two_more() -> None:
    image_base64 = base64.b64encode(b"jpeg").decode()

    async def backend_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/suggestions"
        return httpx.Response(
            200,
            json={
                "intent": "SAFE_EXTENSION",
                "suggestions": [
                    {
                        "label": f"Item {index}",
                        "rationale": "It extends your profile.",
                        "image_base64": image_base64,
                        "mime_type": "image/jpeg",
                    }
                    for index in range(1, 4)
                ],
            },
        )

    class SuggestionMessage:
        def __init__(self) -> None:
            self.photos: list[bytes] = []
            self.captions: list[str] = []
            self.replies: list[str] = []
            self.reply_markups: list[object] = []
            self.events: list[str] = []

        async def reply_photo(self, photo, **kwargs: object) -> None:
            self.photos.append(photo.read())
            self.captions.append(str(kwargs.get("caption")))
            self.events.append("photo")

        async def reply_text(self, text: str, **kwargs: object) -> None:
            self.replies.append(text)
            self.reply_markups.append(kwargs.get("reply_markup"))
            self.events.append("controls")

    class FakeQuery:
        def __init__(self) -> None:
            self.data = "sug:SAFE_EXTENSION"
            self.message = SuggestionMessage()
            self.from_user = SimpleNamespace(id=123, first_name="Vinz", username="vinz")
            self.edits: list[tuple[str, object]] = []

        async def answer(self, *_: object, **__: object) -> None:
            return None

        async def edit_message_text(self, text: str, **kwargs: object) -> None:
            self.edits.append((text, kwargs.get("reply_markup")))

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    query = FakeQuery()
    context = SimpleNamespace(user_data={}, bot_data={"backend_client": client})
    update = SimpleNamespace(callback_query=query)

    run(handle_suggestion_action(update, context))  # type: ignore[arg-type]
    category_markup = query.edits[-1][1]
    assert category_markup.inline_keyboard[1][0].callback_data == "sugc:TOPS"
    assert query.message.photos == []

    query.data = "sugc:TOPS"
    run(handle_suggestion_action(update, context))  # type: ignore[arg-type]
    run(client.close())

    assert query.message.photos == [b"jpeg", b"jpeg", b"jpeg"]
    assert "Suggestion 1" in query.message.captions[0]
    assert context.user_data["suggestion_state"]["generated_count"] == 3
    assert context.user_data["suggestion_state"]["category"] == "TOPS"
    assert query.message.events == ["photo", "photo", "photo", "controls"]
    assert query.edits[-1][0] == "Generation complete. Your reference images are below."
    final_markup = query.message.reply_markups[-1]
    assert final_markup.inline_keyboard[0][0].callback_data == "sug:MORE"
    assert final_markup.inline_keyboard[1][0].callback_data == "sug:FINISH"


def test_suggestion_finish_ends_session_and_removes_controls() -> None:
    class FakeQuery:
        def __init__(self) -> None:
            self.data = "sug:FINISH"
            self.message = SimpleNamespace()
            self.from_user = SimpleNamespace(id=123)
            self.edits: list[tuple[str, object]] = []

        async def answer(self, *_: object, **__: object) -> None:
            return None

        async def edit_message_text(self, text: str, **kwargs: object) -> None:
            self.edits.append((text, kwargs.get("reply_markup")))

    query = FakeQuery()
    context = SimpleNamespace(
        user_data={
            "suggestion_state": {
                "intent": "SAFE_EXTENSION",
                "category": "TOPS",
                "labels": ["Item 1", "Item 2", "Item 3"],
                "generated_count": 3,
            }
        }
    )

    run(
        handle_suggestion_action(
            SimpleNamespace(callback_query=query),
            context,
        )
    )  # type: ignore[arg-type]

    assert "suggestion_state" not in context.user_data
    assert query.edits == [
        (
            "Suggestion session finished. Use /suggestion whenever you want more ideas.",
            None,
        )
    ]


def test_wardrobe_lists_and_opens_stored_item_photo() -> None:
    item_id = "31a2b686-ffb6-4ab4-a7be-876540bca13a"

    async def backend_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/wardrobe":
            return httpx.Response(
                200,
                json={
                    "items": [{"item_id": item_id, "label": "Blue shirt"}],
                    "page": 1,
                    "page_size": 10,
                    "has_previous": False,
                    "has_next": False,
                },
            )
        if request.url.path.endswith("/image"):
            return httpx.Response(
                200,
                content=b"jpeg",
                headers={"Content-Type": "image/jpeg"},
            )
        return httpx.Response(
            200,
            json={
                "item_id": item_id,
                "created_at": "2026-10-17T00:00:00Z",
                "corrected_fields": [],
                "features": {
                    "itemName": "Blue shirt",
                    "itemType": {"value": "shirt", "confidence": 1.0},
                    "colours": [
                        {
                            "name": "blue",
                            "hex": "#0000FF",
                            "proportion": 1.0,
                            "confidence": 1.0,
                        }
                    ],
                },
            },
        )

    class WardrobeMessage(FakeMessage):
        def __init__(self) -> None:
            super().__init__()
            self.photos: list[bytes] = []
            self.photo_markups: list[object] = []

        async def reply_photo(self, photo, **kwargs: object) -> None:
            self.photos.append(photo.read())
            self.photo_markups.append(kwargs.get("reply_markup"))

    class FakeQuery:
        def __init__(self, message: WardrobeMessage) -> None:
            self.data = f"wd:{item_id}"
            self.message = message
            self.from_user = SimpleNamespace(id=123, first_name="Vinz", username="vinz")
            self.edits: list[str] = []

        async def answer(self, *_: object, **__: object) -> None:
            return None

        async def edit_message_text(self, text: str, **_: object) -> None:
            self.edits.append(text)

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    message = WardrobeMessage()
    user = SimpleNamespace(id=123, first_name="Vinz", username="vinz")
    context = SimpleNamespace(user_data={}, bot_data={"backend_client": client})
    run(
        browse_wardrobe(
            SimpleNamespace(effective_message=message, effective_user=user),
            context,
        )
    )  # type: ignore[arg-type]
    query = FakeQuery(message)
    run(
        handle_wardrobe_action(SimpleNamespace(callback_query=query), context)
    )  # type: ignore[arg-type]
    run(client.close())

    assert message.reply_markups[0].inline_keyboard[0][0].callback_data == f"wd:{item_id}"
    assert message.photos == [b"jpeg"]
    assert message.photo_markups[0].inline_keyboard[0][0].callback_data == f"wde:{item_id}"
    assert message.photo_markups[0].inline_keyboard[0][0].text == "Edit Item Details"


def test_editing_shows_current_value_and_returns_to_field_menu() -> None:
    item_id = "31a2b686-ffb6-4ab4-a7be-876540bca13a"

    async def backend_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/correction-options"):
            return httpx.Response(
                200,
                json=[
                    {
                        "field": "materials",
                        "input_hint": "Send materials separated by commas.",
                        "examples": ["linen", "cotton blend"],
                    }
                ],
            )
        return httpx.Response(
            200,
            json={
                "item_id": item_id,
                "created_at": "2026-10-17T00:00:00Z",
                "corrected_fields": [],
                "features": {
                    "itemName": "Blue shirt",
                    "itemType": {"value": "shirt", "confidence": 1.0},
                    "colours": [],
                    "materials": [{"value": "cotton", "confidence": 1.0}],
                },
            },
        )

    class PhotoMessage:
        photo = [object()]

    class FakeQuery:
        def __init__(self) -> None:
            self.data = f"wdf:materials:{item_id}"
            self.message = PhotoMessage()
            self.from_user = SimpleNamespace(id=123, first_name="Vinz", username="vinz")
            self.captions: list[tuple[str, object]] = []

        async def answer(self, *_: object, **__: object) -> None:
            return None

        async def edit_message_caption(self, caption: str, **kwargs: object) -> None:
            self.captions.append((caption, kwargs.get("reply_markup")))

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    context = SimpleNamespace(
        user_data={"wardrobe_state": {"page": 1, "item_id": item_id}},
        bot_data={"backend_client": client},
    )
    query = FakeQuery()
    run(handle_wardrobe_action(SimpleNamespace(callback_query=query), context))

    assert "Current Value:</b> Cotton" in query.captions[-1][0]
    assert "Examples You Can Enter:</b> linen | cotton blend" in query.captions[-1][0]
    assert query.captions[-1][1].inline_keyboard[0][0].text == "Back to Editable Fields"

    query.data = "wca"
    run(handle_wardrobe_action(SimpleNamespace(callback_query=query), context))
    run(client.close())

    assert context.user_data["wardrobe_state"]["stage"] == "choose_field"
    assert query.captions[-1][1].inline_keyboard[-1][0].text == "Back to Item"


def test_back_to_item_reopens_photo_from_text_editing_message() -> None:
    item_id = "31a2b686-ffb6-4ab4-a7be-876540bca13a"

    async def backend_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/image"):
            return httpx.Response(
                200,
                content=b"jpeg",
                headers={"Content-Type": "image/jpeg"},
            )
        return httpx.Response(
            200,
            json={
                "item_id": item_id,
                "created_at": "2026-10-17T00:00:00Z",
                "corrected_fields": [],
                "features": {
                    "itemName": "Blue shirt",
                    "itemType": {"value": "shirt", "confidence": 1.0},
                    "colours": [],
                },
            },
        )

    class TextMessage:
        photo: list[object] = []

        def __init__(self) -> None:
            self.photos: list[bytes] = []

        async def reply_photo(self, photo, **_: object) -> None:
            self.photos.append(photo.read())

    class FakeQuery:
        def __init__(self) -> None:
            self.data = "wdi"
            self.message = TextMessage()
            self.from_user = SimpleNamespace(id=123, first_name="Vinz", username="vinz")
            self.edits: list[str] = []

        async def answer(self, *_: object, **__: object) -> None:
            return None

        async def edit_message_text(self, text: str, **_: object) -> None:
            self.edits.append(text)

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    context = SimpleNamespace(
        user_data={"wardrobe_state": {"page": 1, "item_id": item_id}},
        bot_data={"backend_client": client},
    )
    query = FakeQuery()

    run(handle_wardrobe_action(SimpleNamespace(callback_query=query), context))
    run(client.close())

    assert query.edits == ["Item details reopened below."]
    assert query.message.photos == [b"jpeg"]
    assert context.user_data["wardrobe_state"]["stage"] == "view"


def test_guided_correction_requires_preview_then_confirmation() -> None:
    item_id = "31a2b686-ffb6-4ab4-a7be-876540bca13a"

    async def backend_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(
            "/corrections" if not request.url.path.endswith("/preview") else "/preview"
        )
        payload = {
            "item_id": item_id,
            "field": "item_name",
            "features": {
                "itemName": "Travel shirt",
                "itemType": {"value": "shirt", "confidence": 1.0},
                "colours": [],
            },
        }
        if not request.url.path.endswith("/preview"):
            payload.update({"profile_status": "READY", "usable_item_count": 6})
        return httpx.Response(200, json=payload)

    class CorrectionMessage(FakeMessage):
        def __init__(self) -> None:
            super().__init__()
            self.text = "Travel shirt"

    class FakeQuery:
        def __init__(self) -> None:
            self.data = "wcc:y"
            self.message = SimpleNamespace()
            self.from_user = SimpleNamespace(id=123, first_name="Vinz", username="vinz")
            self.edits: list[str] = []

        async def answer(self, *_: object, **__: object) -> None:
            return None

        async def edit_message_text(self, text: str, **_: object) -> None:
            self.edits.append(text)

    client = AuraBackendClient(
        base_url="http://backend.test",
        timeout_seconds=10,
        transport=httpx.MockTransport(backend_handler),
    )
    context = SimpleNamespace(
        user_data={
            "wardrobe_state": {
                "page": 1,
                "item_id": item_id,
                "field": "item_name",
                "current_value": "Blue shirt",
                "stage": "awaiting_value",
            }
        },
        bot_data={"backend_client": client},
    )
    message = CorrectionMessage()
    user = SimpleNamespace(id=123, first_name="Vinz", username="vinz")
    run(
        handle_correction_text(
            SimpleNamespace(effective_message=message, effective_user=user),
            context,
        )
    )  # type: ignore[arg-type]

    assert context.user_data["wardrobe_state"]["stage"] == "confirm"
    assert message.reply_markups[0].inline_keyboard[0][0].callback_data == "wcc:y"
    assert "Current Value:</b> Blue shirt" in message.replies[-1]
    assert "New Value:</b> Travel shirt" in message.replies[-1]

    query = FakeQuery()
    run(
        handle_wardrobe_action(SimpleNamespace(callback_query=query), context)
    )  # type: ignore[arg-type]
    run(client.close())

    assert "Correction saved" in query.edits[-1]
    assert context.user_data["wardrobe_state"] == {"page": 1}
