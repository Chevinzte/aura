from asyncio import run
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aura_backend.ai.contracts import GeneratedImage
from aura_backend.application.suggestions import (
    SuggestionCategory,
    SuggestionIntent,
    SuggestionProfileNotReady,
    SuggestionService,
)
from aura_backend.repositories.supabase import FeaturePipelineVersion


PIPELINE = FeaturePipelineVersion(
    vision_provider="gateway",
    vision_model="vision-model",
    vision_prompt_version=1,
    feature_schema_version=1,
    embedding_provider="gateway",
    embedding_model="embedding-model",
    embedding_dimensions=2,
    embedding_schema_version=1,
)


class FakeRepository:
    def __init__(self, *, ready: bool = True) -> None:
        self.user_id = uuid4()
        self.ready = ready

    def find_or_create_user(self, *_: object) -> dict[str, str]:
        return {"id": str(self.user_id)}

    def get_active_profile(self, **_: object):
        if not self.ready:
            return None
        profile = SimpleNamespace(
            colours=[SimpleNamespace(name="cream")],
            style_traits=[SimpleNamespace(value="minimal")],
            patterns=[SimpleNamespace(value="plain")],
            materials=[SimpleNamespace(value="cotton")],
            textures=[SimpleNamespace(value="smooth")],
            shape_traits=[SimpleNamespace(value="structured")],
            decorative_details=[],
            aesthetic_signals=[SimpleNamespace(value="minimalist")],
        )
        return SimpleNamespace(profile=profile)

    def list_profile_inputs(self, **_: object) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                features=SimpleNamespace(
                    item_type=SimpleNamespace(value="shirt"),
                )
            )
        ]


class FakeImageGenerator:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> GeneratedImage:
        self.prompts.append(prompt)
        return GeneratedImage(data=b"jpeg", mime_type="image/jpeg")


def test_suggestion_service_uses_full_profile_and_avoids_owned_type() -> None:
    generator = FakeImageGenerator()
    service = SuggestionService(
        repository=FakeRepository(),
        image_generator=generator,
        pipeline=PIPELINE,
    )

    result = run(
        service.generate(
            telegram_user_id=123,
            display_name="Vinz",
            intent=SuggestionIntent.SAFE_EXTENSION,
            category=SuggestionCategory.TOPS,
            count=3,
        )
    )

    assert len(result.suggestions) == 3
    assert result.category == SuggestionCategory.TOPS
    assert result.suggestions[0].label == "Fine-knit top"
    assert {suggestion.label for suggestion in result.suggestions} <= {
        "Relaxed cotton shirt",
        "Fine-knit top",
        "Clean-lined blouse",
        "Ribbed long-sleeve top",
        "Minimal polo shirt",
    }
    assert all("cream" in prompt for prompt in generator.prompts)
    assert all("minimal" in prompt for prompt in generator.prompts)
    assert all("cotton" in prompt for prompt in generator.prompts)
    assert all("Show one item only" in prompt for prompt in generator.prompts)
    assert all("No person" in prompt for prompt in generator.prompts)


def test_suggestion_service_requires_ready_profile() -> None:
    service = SuggestionService(
        repository=FakeRepository(ready=False),
        image_generator=FakeImageGenerator(),
        pipeline=PIPELINE,
    )

    with pytest.raises(SuggestionProfileNotReady):
        run(
            service.generate(
                telegram_user_id=123,
                display_name="Vinz",
                intent=SuggestionIntent.SURPRISE_ME,
                count=3,
            )
        )
