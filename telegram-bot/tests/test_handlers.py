from asyncio import run
from types import SimpleNamespace

import httpx

from aura_telegram.backend import AuraBackendClient
from aura_telegram.handlers import show_profile


class FakeMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


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
