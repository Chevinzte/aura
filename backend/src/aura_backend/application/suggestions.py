from __future__ import annotations

from asyncio import gather
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from aura_backend.ai.contracts import GeneratedImage, ImageGenerationError, ImageGenerator
from aura_backend.application.matching import ActiveProfile
from aura_backend.application.profiles import ProfileInput
from aura_backend.domain.models import AestheticProfileV1, WeightedColour, WeightedFeature
from aura_backend.repositories.supabase import FeaturePipelineVersion


class SuggestionIntent(StrEnum):
    SAFE_EXTENSION = "SAFE_EXTENSION"
    INTENTIONAL_CONTRAST = "INTENTIONAL_CONTRAST"
    SURPRISE_ME = "SURPRISE_ME"


class SuggestionCategory(StrEnum):
    ANY = "ANY"
    TOPS = "TOPS"
    OUTERWEAR = "OUTERWEAR"
    PANTS = "PANTS"
    ACCESSORIES = "ACCESSORIES"
    FOOTWEAR = "FOOTWEAR"


class SuggestionProfileNotReady(RuntimeError):
    """Raised when the user has no compatible active profile."""


class SuggestionPersistenceError(RuntimeError):
    """Raised when profile evidence cannot be loaded."""


class SuggestionGenerationUnavailable(RuntimeError):
    """Raised when no requested reference image can be generated."""


@dataclass(frozen=True, slots=True)
class WardrobeSuggestion:
    label: str
    rationale: str
    image: GeneratedImage


@dataclass(frozen=True, slots=True)
class SuggestionResult:
    intent: SuggestionIntent
    category: SuggestionCategory
    suggestions: list[WardrobeSuggestion]


@dataclass(frozen=True, slots=True)
class _SuggestionPlan:
    label: str
    item_type: str
    category: SuggestionCategory
    rationale: str
    prompt: str


class SuggestionRepository(Protocol):
    def find_or_create_user(
        self, telegram_user_id: int, display_name: str | None
    ) -> dict[str, Any]: ...

    def get_active_profile(
        self, *, user_id: UUID, pipeline: FeaturePipelineVersion
    ) -> ActiveProfile | None: ...

    def list_profile_inputs(
        self, *, user_id: UUID, pipeline: FeaturePipelineVersion
    ) -> list[ProfileInput]: ...


class SuggestionService:
    """Plan profile-guided wardrobe ideas and generate transient references."""

    _catalog = (
        ("Relaxed cotton shirt", "shirt", SuggestionCategory.TOPS),
        ("Fine-knit top", "knit top", SuggestionCategory.TOPS),
        ("Clean-lined blouse", "blouse", SuggestionCategory.TOPS),
        ("Ribbed long-sleeve top", "long-sleeve top", SuggestionCategory.TOPS),
        ("Minimal polo shirt", "polo shirt", SuggestionCategory.TOPS),
        ("Lightweight overshirt", "overshirt", SuggestionCategory.OUTERWEAR),
        ("Clean-lined jacket", "jacket", SuggestionCategory.OUTERWEAR),
        ("Structured blazer", "blazer", SuggestionCategory.OUTERWEAR),
        ("Cropped utility jacket", "utility jacket", SuggestionCategory.OUTERWEAR),
        ("Longline coat", "coat", SuggestionCategory.OUTERWEAR),
        ("Relaxed tailored trousers", "trousers", SuggestionCategory.PANTS),
        ("Wide-leg pants", "wide-leg pants", SuggestionCategory.PANTS),
        ("Straight-leg jeans", "jeans", SuggestionCategory.PANTS),
        ("Refined cargo pants", "cargo pants", SuggestionCategory.PANTS),
        ("Tapered ankle pants", "ankle pants", SuggestionCategory.PANTS),
        ("Structured shoulder bag", "shoulder bag", SuggestionCategory.ACCESSORIES),
        ("Compact crossbody bag", "crossbody bag", SuggestionCategory.ACCESSORIES),
        ("Textured scarf", "scarf", SuggestionCategory.ACCESSORIES),
        ("Minimal leather belt", "belt", SuggestionCategory.ACCESSORIES),
        ("Sculptural everyday earrings", "earrings", SuggestionCategory.ACCESSORIES),
        ("Low-profile sneakers", "sneakers", SuggestionCategory.FOOTWEAR),
        ("Polished loafers", "loafers", SuggestionCategory.FOOTWEAR),
        ("Clean ankle boots", "ankle boots", SuggestionCategory.FOOTWEAR),
        ("Minimal flat shoes", "flat shoes", SuggestionCategory.FOOTWEAR),
        ("Refined sandals", "sandals", SuggestionCategory.FOOTWEAR),
    )

    def __init__(
        self,
        *,
        repository: SuggestionRepository,
        image_generator: ImageGenerator,
        pipeline: FeaturePipelineVersion,
    ) -> None:
        self._repository = repository
        self._image_generator = image_generator
        self._pipeline = pipeline

    async def generate(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        intent: SuggestionIntent,
        count: int,
        category: SuggestionCategory = SuggestionCategory.ANY,
        exclude_labels: list[str] | None = None,
    ) -> SuggestionResult:
        if not 1 <= count <= 3:
            raise ValueError("count must be between one and three")
        try:
            user = self._repository.find_or_create_user(telegram_user_id, display_name)
            user_id = UUID(str(user["id"]))
            active_profile = self._repository.get_active_profile(
                user_id=user_id,
                pipeline=self._pipeline,
            )
            inputs = self._repository.list_profile_inputs(
                user_id=user_id,
                pipeline=self._pipeline,
            )
        except Exception as error:
            raise SuggestionPersistenceError("Could not load suggestion evidence") from error
        if active_profile is None:
            raise SuggestionProfileNotReady("A ready profile is required")

        plans = self._build_plans(
            profile=active_profile.profile,
            inputs=inputs,
            intent=intent,
            category=category,
            count=count,
            exclude_labels=exclude_labels or [],
        )
        async def generate_plan(plan: _SuggestionPlan) -> WardrobeSuggestion | None:
            try:
                image = await self._image_generator.generate(plan.prompt)
            except ImageGenerationError:
                return None
            return WardrobeSuggestion(
                label=plan.label,
                rationale=plan.rationale,
                image=image,
            )

        generated = await gather(*(generate_plan(plan) for plan in plans))
        suggestions = [suggestion for suggestion in generated if suggestion is not None]
        if not suggestions:
            raise SuggestionGenerationUnavailable("No reference images were generated")
        return SuggestionResult(
            intent=intent,
            category=category,
            suggestions=suggestions,
        )

    def _build_plans(
        self,
        *,
        profile: AestheticProfileV1,
        inputs: list[ProfileInput],
        intent: SuggestionIntent,
        category: SuggestionCategory,
        count: int,
        exclude_labels: list[str],
    ) -> list[_SuggestionPlan]:
        excluded = {_normalize(value) for value in exclude_labels}
        owned_types = {_normalize(item.features.item_type.value) for item in inputs}
        category_catalog = [
            item
            for item in self._catalog
            if category == SuggestionCategory.ANY or item[2] == category
        ]
        rotation = {
            SuggestionIntent.SAFE_EXTENSION: 0,
            SuggestionIntent.INTENTIONAL_CONTRAST: 2,
            SuggestionIntent.SURPRISE_ME: 4,
        }[intent]
        catalog = category_catalog[rotation:] + category_catalog[:rotation]
        available = [
            item
            for item in catalog
            if _normalize(item[0]) not in excluded
            and not _matches_owned_type(item[1], owned_types)
        ]
        if len(available) < count:
            available.extend(
                item
                for item in catalog
                if _normalize(item[0]) not in excluded and item not in available
            )

        return [
            self._plan(
                profile=profile,
                intent=intent,
                label=label,
                item_type=item_type,
                category=item_category,
            )
            for label, item_type, item_category in available[:count]
        ]

    def _plan(
        self,
        *,
        profile: AestheticProfileV1,
        intent: SuggestionIntent,
        label: str,
        item_type: str,
        category: SuggestionCategory,
    ) -> _SuggestionPlan:
        colours = _values(profile.colours, "name")
        styles = _values(profile.style_traits)
        patterns = _values(profile.patterns)
        materials = _values(profile.materials)
        textures = _values(profile.textures)
        shapes = _values(profile.shape_traits)
        details = _values(profile.decorative_details)
        influences = _values(profile.aesthetic_signals)

        familiar = ", ".join(styles[:2] or influences[:2]) or "the user's established style"
        if intent == SuggestionIntent.SAFE_EXTENSION:
            direction = "Keep the design closely aligned with these established preferences."
            rationale = f"Extends your {familiar} preferences with an easy new wardrobe category."
        elif intent == SuggestionIntent.INTENTIONAL_CONTRAST:
            accent = _contrast_colour(colours)
            direction = (
                f"Introduce a controlled {accent} accent or one bolder detail while keeping "
                "the silhouette and finish coherent with the profile."
            )
            rationale = (
                f"Adds a controlled {accent} contrast while retaining your {familiar} foundation."
            )
        else:
            direction = (
                "Combine the familiar profile traits with one tasteful unexpected texture, "
                "shape, or accent colour."
            )
            rationale = (
                f"Explores a fresh variation of your {familiar} preferences without becoming an outfit."
            )

        visual_profile = "; ".join(
            part
            for part in (
                _prompt_part("palette", colours),
                _prompt_part("style traits", styles),
                _prompt_part("patterns", patterns),
                _prompt_part("materials", materials),
                _prompt_part("textures", textures),
                _prompt_part("shape traits", shapes),
                _prompt_part("details", details),
                _prompt_part("style influences", influences),
            )
            if part
        )
        prompt = (
            f"Square 1:1 clean studio product photograph of exactly one {item_type}. "
            f"Aesthetic profile: {visual_profile}. {direction} "
            "The item must be realistic, wearable, centered, and fully visible on a neutral "
            "light-gray seamless background with soft diffused lighting. Show one item only. "
            "No person, hands, mannequin, outfit, additional objects, brand, logo, text, "
            "watermark, packaging, price, or retailer imagery."
        )
        return _SuggestionPlan(
            label=label,
            item_type=item_type,
            category=category,
            rationale=rationale,
            prompt=prompt,
        )


def _values(
    values: list[WeightedColour] | list[WeightedFeature],
    field_name: str = "value",
) -> list[str]:
    return [
        str(getattr(value, field_name)).replace("_", " ")
        for value in values[:3]
    ]


def _prompt_part(label: str, values: list[str]) -> str:
    return f"{label}: {', '.join(values)}" if values else ""


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def _matches_owned_type(item_type: str, owned_types: set[str]) -> bool:
    normalized = _normalize(item_type)
    return any(normalized in owned or owned in normalized for owned in owned_types)


def _contrast_colour(profile_colours: list[str]) -> str:
    existing = {_normalize(colour) for colour in profile_colours}
    return next(
        (
            colour
            for colour in (
                "cobalt blue",
                "deep burgundy",
                "forest green",
                "warm ochre",
                "soft lavender",
            )
            if _normalize(colour) not in existing
        ),
        "contrasting accent colour",
    )
