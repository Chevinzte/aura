from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import get_close_matches
from enum import StrEnum
import re
from typing import Any, Protocol
from uuid import UUID, uuid4

from aura_backend.ai.canonical_text import build_canonical_embedding_text
from aura_backend.ai.contracts import EmbeddingProvider, ImageInput
from aura_backend.application.item_analysis import ItemAnalysisService
from aura_backend.application.profiles import ProfileRebuildResult, ProfileService
from aura_backend.domain.models import (
    ColourObservation,
    DecorativeDetailObservation,
    DecorativeDetailValue,
    ItemTypeObservation,
    ItemVisualFeaturesV1,
    MaterialObservation,
    MaterialValue,
    PatternObservation,
    PatternValue,
    ShapeTraitObservation,
    ShapeTraitValue,
    StyleTraitObservation,
    StyleTraitValue,
    TextureObservation,
    TextureValue,
)
from aura_backend.media.images import ImageValidator
from aura_backend.media.storage import ImageStorage
from aura_backend.repositories.supabase import FeaturePipelineVersion


class CorrectionField(StrEnum):
    ITEM_NAME = "item_name"
    ITEM_TYPE = "item_type"
    COLOURS = "colours"
    PATTERNS = "patterns"
    MATERIALS = "materials"
    TEXTURES = "textures"
    STYLE_TRAITS = "style_traits"
    SHAPE_TRAITS = "shape_traits"
    DECORATIVE_DETAILS = "decorative_details"


CORRECTION_EXAMPLES: dict[CorrectionField, list[str]] = {
    CorrectionField.ITEM_NAME: ["Navy travel overshirt"],
    CorrectionField.ITEM_TYPE: ["T-shirt", "Overshirt", "Backpack"],
    CorrectionField.COLOURS: ["navy", "cream, olive", "black, white"],
    CorrectionField.PATTERNS: ["plain", "striped, colour block", "plaid"],
    CorrectionField.MATERIALS: ["linen", "cotton blend", "faux leather"],
    CorrectionField.TEXTURES: ["smooth", "ribbed", "fuzzy, chunky knit"],
    CorrectionField.STYLE_TRAITS: ["casual, minimal", "preppy", "streetwear"],
    CorrectionField.SHAPE_TRAITS: ["boxy, cropped", "fitted", "wide leg"],
    CorrectionField.DECORATIVE_DETAILS: ["buttons", "zipper, pockets", "lace trim"],
}


_CONTROLLED_FIELDS = {
    CorrectionField.PATTERNS: (PatternObservation, PatternValue, 5),
    CorrectionField.MATERIALS: (MaterialObservation, MaterialValue, 5),
    CorrectionField.TEXTURES: (TextureObservation, TextureValue, 5),
    CorrectionField.STYLE_TRAITS: (StyleTraitObservation, StyleTraitValue, 6),
    CorrectionField.SHAPE_TRAITS: (ShapeTraitObservation, ShapeTraitValue, 5),
    CorrectionField.DECORATIVE_DETAILS: (
        DecorativeDetailObservation,
        DecorativeDetailValue,
        5,
    ),
}


_VALUE_ALIASES: dict[CorrectionField, dict[str, str]] = {
    CorrectionField.PATTERNS: {
        "animal": "animal_print",
        "animal_pattern": "animal_print",
        "check": "checkered",
        "checks": "checkered",
        "checked": "checkered",
        "color_block": "colour_block",
        "color_blocked": "colour_block",
        "colour_blocked": "colour_block",
        "leopard": "leopard_print",
        "polka_dots": "polka_dot",
        "stripes": "striped",
        "zebra": "zebra_print",
    },
    CorrectionField.MATERIALS: {
        "cotton_mix": "cotton_blend",
        "fake_leather": "faux_leather",
        "imitation_leather": "faux_leather",
        "leatherette": "faux_leather",
        "linen_mix": "linen_blend",
        "lycra": "elastane",
        "pleather": "faux_leather",
        "spandex": "elastane",
        "vegan_leather": "faux_leather",
        "wool_mix": "wool_blend",
    },
    CorrectionField.TEXTURES: {
        "chunky": "chunky_knit",
        "crinkle": "crinkled",
        "distress": "distressed",
        "fluffy": "fuzzy",
        "shiny": "glossy",
        "silken": "silky",
    },
    CorrectionField.STYLE_TRAITS: {
        "boho": "bohemian",
        "dressy": "formal",
        "glam": "glamorous",
        "minimalist": "minimal",
        "retro": "vintage",
        "smart": "smart_casual",
        "urban": "streetwear",
    },
    CorrectionField.SHAPE_TRAITS: {
        "asymmetrical": "asymmetric",
        "baggy": "oversized",
        "close_fitting": "fitted",
        "loose": "relaxed",
        "skinny": "slim",
        "wide_legged": "wide_leg",
    },
    CorrectionField.DECORATIVE_DETAILS: {
        "beads": "beading",
        "button": "buttons",
        "cut_out": "cutout",
        "frills": "frill",
        "ruffle": "frill",
        "ruffles": "frill",
        "sequin": "sequins",
        "studs": "stud",
        "tassels": "tassel",
        "zip": "zipper",
    },
}


_ITEM_TYPE_ALIASES = {
    "button_down": "button-down shirt",
    "button_down_shirt": "button-down shirt",
    "jumper": "sweater",
    "purse": "handbag",
    "tee": "t-shirt",
    "t_shirt": "t-shirt",
    "tank": "tank top",
    "trainers": "sneakers",
    "trousers": "pants",
}


_COLOUR_HEX = {
    "baby_blue": "#89CFF0",
    "beige": "#F5F5DC",
    "black": "#000000",
    "blue": "#0000FF",
    "blush": "#DE5D83",
    "brown": "#8B4513",
    "burgundy": "#800020",
    "charcoal": "#36454F",
    "cobalt": "#0047AB",
    "coral": "#FF7F50",
    "cream": "#FFFDD0",
    "dark_green": "#006400",
    "emerald": "#50C878",
    "forest_green": "#228B22",
    "gold": "#D4AF37",
    "green": "#008000",
    "grey": "#808080",
    "ivory": "#FFFFF0",
    "indigo": "#4B0082",
    "khaki": "#C3B091",
    "lavender": "#E6E6FA",
    "lilac": "#C8A2C8",
    "lime": "#00FF00",
    "magenta": "#FF00FF",
    "maroon": "#800000",
    "mauve": "#E0B0FF",
    "mint": "#98FF98",
    "mustard": "#FFDB58",
    "navy": "#000080",
    "nude": "#E3BC9A",
    "oatmeal": "#D8C8A8",
    "olive": "#808000",
    "orange": "#FFA500",
    "peach": "#FFE5B4",
    "pink": "#FFC0CB",
    "purple": "#800080",
    "powder_blue": "#B0E0E6",
    "red": "#FF0000",
    "royal_blue": "#4169E1",
    "rust": "#B7410E",
    "sage": "#9CAF88",
    "silver": "#C0C0C0",
    "sky_blue": "#87CEEB",
    "tan": "#D2B48C",
    "taupe": "#8B8589",
    "teal": "#008080",
    "terracotta": "#E2725B",
    "turquoise": "#40E0D0",
    "violet": "#8F00FF",
    "white": "#FFFFFF",
    "yellow": "#FFFF00",
}


_COLOUR_ALIASES = {
    "camel": "tan",
    "chocolate": "brown",
    "dark_blue": "navy",
    "denim_blue": "blue",
    "gray": "grey",
    "light_blue": "sky_blue",
    "light_pink": "blush",
    "off_white": "ivory",
    "rose": "pink",
    "wine": "burgundy",
}


class WardrobeItemNotFound(RuntimeError):
    """Raised when an owned item is unavailable to the requesting user."""


class InvalidCorrection(ValueError):
    """Raised when guided correction values violate the feature contract."""


class WardrobePersistenceError(RuntimeError):
    """Raised when wardrobe state cannot be loaded or changed safely."""


@dataclass(frozen=True, slots=True)
class WardrobeItemSummary:
    item_id: UUID
    label: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WardrobePage:
    items: list[WardrobeItemSummary]
    page: int
    page_size: int
    has_previous: bool
    has_next: bool


@dataclass(frozen=True, slots=True)
class WardrobeItemDetail:
    item_id: UUID
    created_at: datetime
    features: ItemVisualFeaturesV1
    corrected_fields: list[CorrectionField]
    revision_kind: str | None = None


@dataclass(frozen=True, slots=True)
class WardrobeImage:
    data: bytes
    mime_type: str


@dataclass(frozen=True, slots=True)
class CorrectionPreview:
    item_id: UUID
    field: CorrectionField
    features: ItemVisualFeaturesV1


@dataclass(frozen=True, slots=True)
class CorrectionResult:
    item_id: UUID
    field: CorrectionField
    features: ItemVisualFeaturesV1
    profile: ProfileRebuildResult


@dataclass(frozen=True, slots=True)
class ReanalysisPreview:
    preview_id: UUID
    item_id: UUID
    current_features: ItemVisualFeaturesV1
    proposed_features: ItemVisualFeaturesV1
    replaces_manual_corrections: bool


@dataclass(frozen=True, slots=True)
class ReanalysisResult:
    item_id: UUID
    features: ItemVisualFeaturesV1
    profile: ProfileRebuildResult


@dataclass(frozen=True, slots=True)
class WardrobeItemRecord:
    item_id: UUID
    user_id: UUID
    source_features_id: UUID
    storage_path: str
    mime_type: str
    created_at: datetime
    features: ItemVisualFeaturesV1
    corrected_fields: list[CorrectionField]
    active_correction_id: UUID | None = None
    revision_kind: str | None = None


class WardrobeRepository(Protocol):
    def find_or_create_user(
        self, telegram_user_id: int, display_name: str | None
    ) -> dict[str, Any]: ...

    def list_owned_wardrobe_items(
        self,
        *,
        user_id: UUID,
        pipeline: FeaturePipelineVersion,
        limit: int,
        offset: int,
    ) -> list[WardrobeItemSummary]: ...

    def get_owned_wardrobe_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        pipeline: FeaturePipelineVersion,
    ) -> WardrobeItemRecord | None: ...

    def activate_item_feature_correction(self, **kwargs: Any) -> dict[str, Any]: ...

    def restore_item_feature_correction(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        correction_id: UUID,
        previous_correction_id: UUID | None,
    ) -> None: ...

    def create_item_reanalysis_preview(self, **kwargs: Any) -> dict[str, Any]: ...

    def activate_item_reanalysis(self, **kwargs: Any) -> dict[str, Any]: ...

    def discard_item_reanalysis(self, **kwargs: Any) -> None: ...


class WardrobeService:
    """Browse owned belongings and apply confirmed, versioned corrections."""

    def __init__(
        self,
        *,
        repository: WardrobeRepository,
        storage: ImageStorage,
        image_validator: ImageValidator,
        item_analysis: ItemAnalysisService,
        embedding_provider: EmbeddingProvider,
        profile_service: ProfileService,
        pipeline: FeaturePipelineVersion,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._image_validator = image_validator
        self._item_analysis = item_analysis
        self._embedding_provider = embedding_provider
        self._profile_service = profile_service
        self._pipeline = pipeline

    def list_items(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        page: int = 1,
        page_size: int = 10,
    ) -> WardrobePage:
        if page < 1 or not 1 <= page_size <= 20:
            raise ValueError("Invalid wardrobe page")
        user_id = self._user_id(telegram_user_id, display_name)
        try:
            items = self._repository.list_owned_wardrobe_items(
                user_id=user_id,
                pipeline=self._pipeline,
                limit=page_size + 1,
                offset=(page - 1) * page_size,
            )
        except Exception as error:
            raise WardrobePersistenceError("Could not list wardrobe items") from error
        return WardrobePage(
            items=items[:page_size],
            page=page,
            page_size=page_size,
            has_previous=page > 1,
            has_next=len(items) > page_size,
        )

    def get_item(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
    ) -> WardrobeItemDetail:
        record = self._record(telegram_user_id, display_name, item_id)
        return WardrobeItemDetail(
            item_id=record.item_id,
            created_at=record.created_at,
            features=record.features,
            corrected_fields=record.corrected_fields,
            revision_kind=record.revision_kind,
        )

    def get_image(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
    ) -> WardrobeImage:
        record = self._record(telegram_user_id, display_name, item_id)
        try:
            data = self._storage.download(record.storage_path)
        except Exception as error:
            raise WardrobePersistenceError("Could not load wardrobe image") from error
        return WardrobeImage(data=data, mime_type=record.mime_type)

    def preview_correction(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
        field: CorrectionField,
        values: list[str],
    ) -> CorrectionPreview:
        record = self._record(telegram_user_id, display_name, item_id)
        return CorrectionPreview(
            item_id=item_id,
            field=field,
            features=self._corrected_features(record.features, field, values),
        )

    async def apply_correction(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
        field: CorrectionField,
        values: list[str],
    ) -> CorrectionResult:
        record = self._record(telegram_user_id, display_name, item_id)
        features = self._corrected_features(record.features, field, values)
        canonical_text = build_canonical_embedding_text(features)
        embedding = await self._embedding_provider.embed(canonical_text)
        corrected_fields = list(dict.fromkeys([*record.corrected_fields, field]))
        correction_id = uuid4()
        try:
            self._repository.activate_item_feature_correction(
                correction_id=correction_id,
                user_id=record.user_id,
                item_id=item_id,
                source_features_id=record.source_features_id,
                corrected_features=features,
                canonical_embedding_text=canonical_text,
                embedding=embedding,
                corrected_fields=corrected_fields,
                pipeline=self._pipeline,
            )
            profile = self._profile_service.rebuild_if_ready(record.user_id)
        except Exception as error:
            try:
                self._repository.restore_item_feature_correction(
                    user_id=record.user_id,
                    item_id=item_id,
                    correction_id=correction_id,
                    previous_correction_id=record.active_correction_id,
                )
            except Exception:
                pass
            raise WardrobePersistenceError("Could not apply item correction") from error
        return CorrectionResult(
            item_id=item_id,
            field=field,
            features=features,
            profile=profile,
        )

    async def preview_reanalysis(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
    ) -> ReanalysisPreview:
        record = self._record(telegram_user_id, display_name, item_id)
        try:
            data = self._storage.download(record.storage_path)
            image = self._image_validator.validate(data, record.mime_type)
        except Exception as error:
            raise WardrobePersistenceError("Could not prepare wardrobe image") from error

        extracted = await self._item_analysis.extract(
            ImageInput(
                data=image.analysis_data,
                mime_type=image.mime_type,
                filename=None,
            )
        )
        preview_id = uuid4()
        try:
            self._repository.create_item_reanalysis_preview(
                revision_id=preview_id,
                user_id=record.user_id,
                item_id=item_id,
                source_features_id=record.source_features_id,
                features=extracted.features,
                canonical_embedding_text=extracted.canonical_embedding_text,
                embedding=extracted.embedding,
                corrected_fields=list(CorrectionField),
                pipeline=self._pipeline,
            )
        except Exception as error:
            raise WardrobePersistenceError("Could not save reanalysis preview") from error
        return ReanalysisPreview(
            preview_id=preview_id,
            item_id=item_id,
            current_features=record.features,
            proposed_features=extracted.features,
            replaces_manual_corrections=bool(record.corrected_fields),
        )

    def confirm_reanalysis(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
        preview_id: UUID,
    ) -> ReanalysisResult:
        record = self._record(telegram_user_id, display_name, item_id)
        try:
            activated = self._repository.activate_item_reanalysis(
                user_id=record.user_id,
                item_id=item_id,
                revision_id=preview_id,
            )
            features = ItemVisualFeaturesV1.model_validate(
                activated.get("corrected_features")
            )
            profile = self._profile_service.rebuild_if_ready(record.user_id)
        except Exception as error:
            try:
                self._repository.restore_item_feature_correction(
                    user_id=record.user_id,
                    item_id=item_id,
                    correction_id=preview_id,
                    previous_correction_id=record.active_correction_id,
                )
            except Exception:
                pass
            raise WardrobePersistenceError("Could not confirm item reanalysis") from error
        return ReanalysisResult(item_id=item_id, features=features, profile=profile)

    def discard_reanalysis(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
        preview_id: UUID,
    ) -> None:
        user_id = self._user_id(telegram_user_id, display_name)
        try:
            self._repository.discard_item_reanalysis(
                user_id=user_id,
                item_id=item_id,
                revision_id=preview_id,
            )
        except Exception as error:
            raise WardrobePersistenceError("Could not discard item reanalysis") from error

    def _record(
        self,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
    ) -> WardrobeItemRecord:
        user_id = self._user_id(telegram_user_id, display_name)
        try:
            record = self._repository.get_owned_wardrobe_item(
                user_id=user_id,
                item_id=item_id,
                pipeline=self._pipeline,
            )
        except Exception as error:
            raise WardrobePersistenceError("Could not load wardrobe item") from error
        if record is None:
            raise WardrobeItemNotFound("Owned wardrobe item was not found")
        return record

    def _user_id(self, telegram_user_id: int, display_name: str | None) -> UUID:
        try:
            user = self._repository.find_or_create_user(telegram_user_id, display_name)
            return UUID(str(user["id"]))
        except Exception as error:
            raise WardrobePersistenceError("Could not load wardrobe user") from error

    def _corrected_features(
        self,
        current: ItemVisualFeaturesV1,
        field: CorrectionField,
        values: list[str],
    ) -> ItemVisualFeaturesV1:
        cleaned = [" ".join(value.strip().split()) for value in values if value.strip()]
        if not cleaned:
            raise InvalidCorrection("At least one corrected value is required")
        data = current.model_dump(by_alias=False, mode="python")
        if field == CorrectionField.ITEM_NAME:
            if len(cleaned) != 1:
                raise InvalidCorrection("Item name requires one value")
            data["item_name"] = cleaned[0][:120]
        elif field == CorrectionField.ITEM_TYPE:
            if len(cleaned) != 1:
                raise InvalidCorrection("Item type requires one value")
            data["item_type"] = ItemTypeObservation(
                value=self._item_type(cleaned[0]),
                confidence=1.0,
            )
        elif field == CorrectionField.COLOURS:
            data["colours"] = self._colours(cleaned)
        else:
            data[field.value] = self._controlled_observations(field, cleaned)
        try:
            return ItemVisualFeaturesV1.model_validate(data)
        except ValueError as error:
            raise InvalidCorrection("Corrected values are invalid") from error

    def _colours(self, values: list[str]) -> list[ColourObservation]:
        if len(values) > 8:
            raise InvalidCorrection("At most eight colours are supported")
        normalized: list[str] = []
        for value in values:
            name = re.sub(r"\s+#[0-9A-Fa-f]{6}$", "", value).strip()
            key = _normalized_key(name)
            key = _COLOUR_ALIASES.get(key, key)
            if key not in _COLOUR_HEX:
                raise InvalidCorrection(
                    _unsupported_message("colours", value, _COLOUR_HEX, _COLOUR_ALIASES)
                )
            if key not in normalized:
                normalized.append(key)
        proportion = 1.0 / len(normalized)
        colours: list[ColourObservation] = []
        for value in normalized:
            colours.append(
                ColourObservation(
                    name=value.replace("_", " "),
                    hex=_COLOUR_HEX[value],
                    proportion=proportion,
                    confidence=1.0,
                )
            )
        return colours

    def _controlled_observations(
        self,
        field: CorrectionField,
        values: list[str],
    ) -> list[Any]:
        observation_type, enum_type, maximum = _CONTROLLED_FIELDS[field]
        if len(values) > maximum:
            raise InvalidCorrection(
                f"{field.value.replace('_', ' ').title()} accepts at most {maximum} values"
            )
        allowed = {member.value for member in enum_type}
        aliases = _VALUE_ALIASES.get(field, {})
        normalized: list[str] = []
        for value in values:
            key = _normalized_key(value)
            canonical = aliases.get(key, key)
            if canonical not in allowed:
                raise InvalidCorrection(
                    _unsupported_message(
                        field.value.replace("_", " "),
                        value,
                        allowed,
                        aliases,
                    )
                )
            if canonical not in normalized:
                normalized.append(canonical)
        return [
            observation_type(value=value, confidence=1.0)
            for value in normalized
        ]

    @staticmethod
    def _item_type(value: str) -> str:
        key = _normalized_key(value)
        return _ITEM_TYPE_ALIASES.get(key, key.replace("_", " "))[:80]


def _normalized_key(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.strip().lower())).strip("_")


def _unsupported_message(
    field: str,
    raw_value: str,
    allowed: Any,
    aliases: dict[str, str],
) -> str:
    choices = sorted(set(allowed) | set(aliases))
    matches = get_close_matches(_normalized_key(raw_value), choices, n=3, cutoff=0.45)
    suggestions = list(dict.fromkeys(aliases.get(match, match) for match in matches))
    display_field = field.replace("_", " ").title()
    message = f'"{raw_value}" is not recognized for {display_field}.'
    if suggestions:
        formatted = ", ".join(value.replace("_", " ").title() for value in suggestions)
        return f"{message} Try: {formatted}."
    examples = CORRECTION_EXAMPLES.get(CorrectionField(field.replace(" ", "_")), [])
    if examples:
        return f"{message} Example: {examples[0]}."
    return message
