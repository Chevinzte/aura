from types import SimpleNamespace
from unittest.mock import MagicMock

from aura_backend.api import dependencies
from aura_backend.application.owned_items import OwnedItemService


def test_owned_item_dependency_returns_service(monkeypatch) -> None:
    settings = SimpleNamespace(
        vision_model="vision-model",
        embedding_model="embedding-model",
        embedding_dimensions=1536,
        max_image_bytes=10_000,
        min_image_dimension=256,
        ai_base_url="https://example.test/v1",
        ai_api_key="test-key",
        ai_timeout_seconds=10.0,
    )
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    monkeypatch.setattr(dependencies, "get_supabase_client", MagicMock)
    dependencies.get_owned_item_service.cache_clear()

    try:
        service = dependencies.get_owned_item_service()
    finally:
        dependencies.get_owned_item_service.cache_clear()

    assert isinstance(service, OwnedItemService)
