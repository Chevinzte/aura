from __future__ import annotations

from asyncio import gather
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Any, Protocol
from uuid import UUID

from aura_backend.ai.contracts import GeneratedImage, ImageGenerationError, ImageGenerator
from aura_backend.application.matching import ActiveProfile
from aura_backend.application.preferences import (
    FashionPresentation,
    parse_fashion_presentation,
)
from aura_backend.application.profiles import ProfileInput
from aura_backend.domain.models import AestheticProfileV1, WeightedColour, WeightedFeature
from aura_backend.repositories.supabase import FeaturePipelineVersion


logger = logging.getLogger(__name__)


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

    def list_recent_suggestion_labels(
        self, *, user_id: UUID, limit: int
    ) -> list[str]: ...

    def record_suggestion_history(
        self,
        *,
        user_id: UUID,
        intent: SuggestionIntent,
        category: SuggestionCategory,
        concepts: list[tuple[str, str]],
    ) -> None: ...


class SuggestionService:
    """Plan profile-guided wardrobe ideas and generate transient references."""

    _catalog = (
        ("Relaxed cotton shirt", "shirt", SuggestionCategory.TOPS),
        ("Fine-knit top", "knit top", SuggestionCategory.TOPS),
        ("Clean button-up shirt", "button-up shirt", SuggestionCategory.TOPS),
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
        ("Polished Derby shoes", "Derby shoes", SuggestionCategory.FOOTWEAR),
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
            fashion_presentation = (
                parse_fashion_presentation(user.get("fashion_presentation"))
                or FashionPresentation.NO_PREFERENCE
            )
            active_profile = self._repository.get_active_profile(
                user_id=user_id,
                pipeline=self._pipeline,
            )
            inputs = self._repository.list_profile_inputs(
                user_id=user_id,
                pipeline=self._pipeline,
            )
            recent_labels = self._repository.list_recent_suggestion_labels(
                user_id=user_id,
                limit=30,
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
            recent_labels=recent_labels,
            fashion_presentation=fashion_presentation,
        )

        async def generate_plan(
            plan: _SuggestionPlan,
        ) -> tuple[_SuggestionPlan, WardrobeSuggestion] | None:
            try:
                image = await self._image_generator.generate(plan.prompt)
            except ImageGenerationError:
                return None
            return (
                plan,
                WardrobeSuggestion(
                    label=plan.label,
                    rationale=plan.rationale,
                    image=image,
                ),
            )

        generated = await gather(*(generate_plan(plan) for plan in plans))
        successful = [result for result in generated if result is not None]
        suggestions = [suggestion for _, suggestion in successful]
        if not suggestions:
            raise SuggestionGenerationUnavailable("No reference images were generated")
        try:
            self._repository.record_suggestion_history(
                user_id=user_id,
                intent=intent,
                category=category,
                concepts=[(plan.label, plan.item_type) for plan, _ in successful],
            )
        except Exception:
            logger.warning(
                "Could not record suggestion history for user %s",
                user_id,
                exc_info=True,
            )
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
        recent_labels: list[str],
        fashion_presentation: FashionPresentation,
    ) -> list[_SuggestionPlan]:
        excluded = {_normalize(value) for value in exclude_labels}
        recent = [_normalize(value) for value in recent_labels]
        recent_set = set(recent)
        owned_types = {_normalize(item.features.item_type.value) for item in inputs}
        category_catalog = [
            item
            for item in self._catalog
            if (category == SuggestionCategory.ANY or item[2] == category)
            and _supports_presentation(item[0], fashion_presentation)
        ]
        intent_rotation = {
            SuggestionIntent.SAFE_EXTENSION: 0,
            SuggestionIntent.INTENTIONAL_CONTRAST: 2,
            SuggestionIntent.SURPRISE_ME: 4,
        }[intent]
        history_seed = sum(
            (position + 1) * sum(ord(character) for character in label)
            for position, label in enumerate(recent)
        )
        rotation = intent_rotation + history_seed
        if category == SuggestionCategory.ANY:
            category_catalog = _spread_categories(category_catalog, rotation)
        position = rotation % len(category_catalog)
        catalog = category_catalog[position:] + category_catalog[:position]
        available = [
            item
            for item in catalog
            if _normalize(item[0]) not in excluded
            and _normalize(item[0]) not in recent_set
            and not _matches_owned_type(item[1], owned_types)
        ]
        if len(available) < count:
            fallback = [
                item
                for item in catalog
                if _normalize(item[0]) not in excluded and item not in available
            ]
            fallback.sort(
                key=lambda item: _recency_rank(item[0], recent),
                reverse=True,
            )
            available.extend(fallback)

        return [
            self._plan(
                profile=profile,
                intent=intent,
                label=label,
                item_type=item_type,
                category=item_category,
                fashion_presentation=fashion_presentation,
                variation_index=history_seed + plan_position,
            )
            for plan_position, (label, item_type, item_category) in enumerate(
                available[:count]
            )
        ]

    def _plan(
        self,
        *,
        profile: AestheticProfileV1,
        intent: SuggestionIntent,
        label: str,
        item_type: str,
        category: SuggestionCategory,
        fashion_presentation: FashionPresentation,
        variation_index: int,
    ) -> _SuggestionPlan:
        profile_colours = _values(profile.colours, "name", limit=None)
        colours = _rotate(_values(profile.colours, "name"), variation_index)
        styles = _rotate(_values(profile.style_traits), variation_index + 1)
        patterns = _rotate(_values(profile.patterns), variation_index + 2)
        materials = _rotate(_values(profile.materials), variation_index + 3)
        textures = _rotate(_values(profile.textures), variation_index + 4)
        shapes = _rotate(_values(profile.shape_traits), variation_index + 5)
        details = _rotate(_values(profile.decorative_details), variation_index + 6)
        influences = _rotate(_values(profile.aesthetic_signals), variation_index + 7)
        variation_focus = _variation_focus(
            colours=colours,
            materials=materials,
            textures=textures,
            shapes=shapes,
            details=details,
            variation_index=variation_index,
        )

        familiar = ", ".join(styles[:2] or influences[:2]) or "the user's established style"
        if intent == SuggestionIntent.SAFE_EXTENSION:
            direction = (
                "Keep the design closely aligned with these established preferences, "
                f"but make this concept distinct by emphasizing {variation_focus}."
            )
            rationale = (
                f"This {item_type} emphasizes {variation_focus} while extending your "
                f"{familiar} preferences."
            )
        elif intent == SuggestionIntent.INTENTIONAL_CONTRAST:
            accent = _contrast_colour(profile_colours, variation_index)
            direction = (
                f"Introduce a controlled {accent} accent or one bolder detail while keeping "
                "the silhouette and finish coherent with the profile. Make this concept "
                f"distinct by emphasizing {variation_focus}."
            )
            rationale = (
                f"This {item_type} introduces a controlled {accent} contrast and "
                f"emphasizes {variation_focus}, while retaining your {familiar} foundation."
            )
        else:
            accent = _contrast_colour(profile_colours, variation_index)
            direction = (
                "Use only one or two familiar profile traits as an anchor, then explore a "
                f"noticeably less familiar silhouette, material, or detail. Emphasize "
                f"{variation_focus} and consider a {accent} accent. Keep the result tasteful "
                "and wearable rather than unrelated to the profile."
            )
            rationale = (
                f"This {item_type} explores {variation_focus} with a {accent} accent, "
                f"anchored by your {familiar} preferences."
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
            f"{_presentation_prompt(fashion_presentation)}"
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
    limit: int | None = 3,
) -> list[str]:
    selected = values if limit is None else values[:limit]
    return [
        str(getattr(value, field_name)).replace("_", " ")
        for value in selected
    ]


def _prompt_part(label: str, values: list[str]) -> str:
    return f"{label}: {', '.join(values)}" if values else ""


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def _rotate(values: list[str], offset: int) -> list[str]:
    if len(values) < 2:
        return values
    position = offset % len(values)
    return values[position:] + values[:position]


def _spread_categories(
    catalog: list[tuple[str, str, SuggestionCategory]],
    offset: int,
) -> list[tuple[str, str, SuggestionCategory]]:
    categories = [
        SuggestionCategory.TOPS,
        SuggestionCategory.OUTERWEAR,
        SuggestionCategory.PANTS,
        SuggestionCategory.ACCESSORIES,
        SuggestionCategory.FOOTWEAR,
    ]
    category_position = offset % len(categories)
    categories = categories[category_position:] + categories[:category_position]
    buckets = {
        category: [item for item in catalog if item[2] == category]
        for category in categories
    }
    spread: list[tuple[str, str, SuggestionCategory]] = []
    while any(buckets.values()):
        for category in categories:
            if buckets[category]:
                spread.append(buckets[category].pop(0))
    return spread


def _recency_rank(label: str, recent_labels: list[str]) -> int:
    normalized = _normalize(label)
    try:
        return recent_labels.index(normalized)
    except ValueError:
        return len(recent_labels) + 1


def _variation_focus(
    *,
    colours: list[str],
    materials: list[str],
    textures: list[str],
    shapes: list[str],
    details: list[str],
    variation_index: int,
) -> str:
    options = [
        f"its {values[0]} {label}"
        for label, values in (
            ("colour", colours),
            ("material", materials),
            ("texture", textures),
            ("shape", shapes),
            ("detail", details),
        )
        if values
    ]
    if not options:
        return "a different proportion or finishing detail"
    return options[variation_index % len(options)]


def _matches_owned_type(item_type: str, owned_types: set[str]) -> bool:
    normalized = _normalize(item_type)
    return any(normalized in owned or owned in normalized for owned in owned_types)


def _contrast_colour(profile_colours: list[str], variation_index: int = 0) -> str:
    existing = {_normalize(colour) for colour in profile_colours}
    choices = [
        colour
        for colour in (
            "cobalt blue",
            "deep burgundy",
            "forest green",
            "warm ochre",
            "soft lavender",
        )
        if _normalize(colour) not in existing
    ]
    if not choices:
        return "contrasting accent colour"
    return choices[variation_index % len(choices)]


def _supports_presentation(
    label: str,
    fashion_presentation: FashionPresentation,
) -> bool:
    exclusions = {
        FashionPresentation.MENSWEAR: {"Clean-lined blouse", "Minimal flat shoes"},
        FashionPresentation.GENDER_NEUTRAL: {
            "Clean-lined blouse",
            "Minimal flat shoes",
        },
        FashionPresentation.WOMENSWEAR: {"Polished Derby shoes"},
        FashionPresentation.NO_PREFERENCE: set(),
    }
    return label not in exclusions[fashion_presentation]


def _presentation_prompt(fashion_presentation: FashionPresentation) -> str:
    instructions = {
        FashionPresentation.MENSWEAR: (
            "Design this specifically for a menswear wardrobe and avoid "
            "womenswear-coded garment cuts. "
        ),
        FashionPresentation.WOMENSWEAR: (
            "Design this specifically for a womenswear wardrobe. "
        ),
        FashionPresentation.GENDER_NEUTRAL: (
            "Use a gender-neutral, versatile fashion presentation. "
        ),
        FashionPresentation.NO_PREFERENCE: "",
    }
    return instructions[fashion_presentation]
