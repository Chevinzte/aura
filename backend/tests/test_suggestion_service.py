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
    def __init__(
        self,
        *,
        ready: bool = True,
        presentation: str | None = None,
        recent_labels: list[str] | None = None,
    ) -> None:
        self.user_id = uuid4()
        self.ready = ready
        self.presentation = presentation
        self.recent_labels = recent_labels or []
        self.recorded_concepts: list[tuple[str, str]] = []

    def find_or_create_user(self, *_: object) -> dict[str, str | None]:
        return {
            "id": str(self.user_id),
            "fashion_presentation": self.presentation,
        }

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

    def list_recent_suggestion_labels(self, **_: object) -> list[str]:
        return self.recent_labels

    def record_suggestion_history(
        self,
        *,
        concepts: list[tuple[str, str]],
        **_: object,
    ) -> None:
        self.recorded_concepts.extend(concepts)


class FakeImageGenerator:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> GeneratedImage:
        self.prompts.append(prompt)
        return GeneratedImage(data=b"jpeg", mime_type="image/jpeg")


def test_suggestion_service_uses_full_profile_and_avoids_owned_type() -> None:
    generator = FakeImageGenerator()
    repository = FakeRepository()
    service = SuggestionService(
        repository=repository,
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
        "Clean button-up shirt",
        "Clean-lined blouse",
        "Ribbed long-sleeve top",
        "Minimal polo shirt",
    }
    assert all("cream" in prompt for prompt in generator.prompts)
    assert all("minimal" in prompt for prompt in generator.prompts)
    assert all("cotton" in prompt for prompt in generator.prompts)
    assert all("Show one item only" in prompt for prompt in generator.prompts)
    assert all("No person" in prompt for prompt in generator.prompts)
    assert len(repository.recorded_concepts) == 3


def test_suggestion_service_avoids_recent_concepts_across_sessions() -> None:
    repository = FakeRepository(
        recent_labels=["Fine-knit top", "Clean button-up shirt"]
    )
    service = SuggestionService(
        repository=repository,
        image_generator=FakeImageGenerator(),
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

    labels = {suggestion.label for suggestion in result.suggestions}
    assert "Fine-knit top" not in labels
    assert "Clean button-up shirt" not in labels


def test_any_category_spreads_suggestions_across_item_categories() -> None:
    result = run(
        SuggestionService(
            repository=FakeRepository(),
            image_generator=FakeImageGenerator(),
            pipeline=PIPELINE,
        ).generate(
            telegram_user_id=123,
            display_name="Vinz",
            intent=SuggestionIntent.SAFE_EXTENSION,
            category=SuggestionCategory.ANY,
            count=3,
        )
    )

    assert {suggestion.label for suggestion in result.suggestions} == {
        "Relaxed tailored trousers",
        "Structured shoulder bag",
        "Low-profile sneakers",
    }


def test_surprise_me_prompt_allows_stronger_controlled_exploration() -> None:
    generator = FakeImageGenerator()
    service = SuggestionService(
        repository=FakeRepository(),
        image_generator=generator,
        pipeline=PIPELINE,
    )

    run(
        service.generate(
            telegram_user_id=123,
            display_name="Vinz",
            intent=SuggestionIntent.SURPRISE_ME,
            category=SuggestionCategory.OUTERWEAR,
            count=1,
        )
    )

    assert "only one or two familiar profile traits" in generator.prompts[0]
    assert "less familiar silhouette, material, or detail" in generator.prompts[0]


def test_contrast_rationales_are_item_specific_and_rotate_accents() -> None:
    result = run(
        SuggestionService(
            repository=FakeRepository(),
            image_generator=FakeImageGenerator(),
            pipeline=PIPELINE,
        ).generate(
            telegram_user_id=123,
            display_name="Vinz",
            intent=SuggestionIntent.INTENTIONAL_CONTRAST,
            category=SuggestionCategory.TOPS,
            count=3,
        )
    )

    rationales = [suggestion.rationale for suggestion in result.suggestions]
    assert len(set(rationales)) == 3
    assert all("This " in rationale for rationale in rationales)
    assert all("while retaining your minimal foundation" in rationale for rationale in rationales)
    accents = {
        accent
        for accent in ("cobalt blue", "deep burgundy", "forest green", "warm ochre", "soft lavender")
        if any(accent in rationale for rationale in rationales)
    }
    assert len(accents) == 3


def test_menswear_preference_filters_catalog_and_constrains_prompts() -> None:
    generator = FakeImageGenerator()
    service = SuggestionService(
        repository=FakeRepository(presentation="MENSWEAR"),
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

    assert "Clean-lined blouse" not in {
        suggestion.label for suggestion in result.suggestions
    }
    assert all("menswear wardrobe" in prompt for prompt in generator.prompts)
    assert all("avoid womenswear-coded garment cuts" in prompt for prompt in generator.prompts)


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
