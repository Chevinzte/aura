from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainModel(BaseModel):
    """Base configuration for persisted and provider-facing domain contracts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ItemSource(StrEnum):
    OWNED = "OWNED"
    CANDIDATE = "CANDIDATE"


class PatternValue(StrEnum):
    ABSTRACT = "abstract"
    ANIMAL_PRINT = "animal_print"
    ARGYLE = "argyle"
    CAMOUFLAGE = "camouflage"
    CHECKERED = "checkered"
    COLOUR_BLOCK = "colour_block"
    FLORAL = "floral"
    GEOMETRIC = "geometric"
    GINGHAM = "gingham"
    GRAPHIC = "graphic"
    HOUNDSTOOTH = "houndstooth"
    LEOPARD_PRINT = "leopard_print"
    LOGO = "logo"
    PAISLEY = "paisley"
    PINSTRIPE = "pinstripe"
    PLAIN = "plain"
    PLAID = "plaid"
    POLKA_DOT = "polka_dot"
    STRIPED = "striped"
    TIE_DYE = "tie_dye"
    TEXTURED = "textured"
    ZEBRA_PRINT = "zebra_print"


class MaterialValue(StrEnum):
    ACRYLIC = "acrylic"
    CANVAS = "canvas"
    CASHMERE = "cashmere"
    CERAMIC = "ceramic"
    CHIFFON = "chiffon"
    COTTON = "cotton"
    COTTON_BLEND = "cotton_blend"
    CORDUROY = "corduroy"
    DENIM = "denim"
    ELASTANE = "elastane"
    FABRIC = "fabric"
    FAUX_LEATHER = "faux_leather"
    GLASS = "glass"
    JERSEY = "jersey"
    KNIT = "knit"
    LACE = "lace"
    LEATHER = "leather"
    LINEN = "linen"
    LINEN_BLEND = "linen_blend"
    MESH = "mesh"
    METAL = "metal"
    NYLON = "nylon"
    PLASTIC = "plastic"
    POLYESTER = "polyester"
    RAYON = "rayon"
    SATIN = "satin"
    SILICONE = "silicone"
    SILK = "silk"
    STRAW = "straw"
    SUEDE = "suede"
    VELVET = "velvet"
    VISCOSE = "viscose"
    WOOL = "wool"
    WOOL_BLEND = "wool_blend"
    WOOD = "wood"


class TextureValue(StrEnum):
    BRUSHED = "brushed"
    CHUNKY_KNIT = "chunky_knit"
    COARSE = "coarse"
    CRINKLED = "crinkled"
    DISTRESSED = "distressed"
    FLEECY = "fleecy"
    FUZZY = "fuzzy"
    GRAINY = "grainy"
    GLOSSY = "glossy"
    MATTE = "matte"
    PLUSH = "plush"
    QUILTED = "quilted"
    RIBBED = "ribbed"
    SHEER = "sheer"
    SILKY = "silky"
    SMOOTH = "smooth"
    SOFT = "soft"
    VELVETY = "velvety"
    WOVEN = "woven"


class ShapeTraitValue(StrEnum):
    ANGULAR = "angular"
    ASYMMETRIC = "asymmetric"
    BOXY = "boxy"
    COMPACT = "compact"
    CROPPED = "cropped"
    DRAPED = "draped"
    ELONGATED = "elongated"
    FITTED = "fitted"
    FLARED = "flared"
    LONGLINE = "longline"
    OVERSIZED = "oversized"
    RELAXED = "relaxed"
    ROUNDED = "rounded"
    SLIM = "slim"
    SOFT = "soft"
    STRAIGHT = "straight"
    STRUCTURED = "structured"
    TAPERED = "tapered"
    VOLUMINOUS = "voluminous"
    WIDE_LEG = "wide_leg"


class DecorativeDetailValue(StrEnum):
    BEADING = "beading"
    BOW = "bow"
    BUCKLE = "buckle"
    BUTTONS = "buttons"
    CHARM = "charm"
    CONTRAST_STITCHING = "contrast_stitching"
    CUTOUT = "cutout"
    EMBROIDERY = "embroidery"
    FRINGE = "fringe"
    FRILL = "frill"
    GOLD_TONE_HARDWARE = "gold_tone_hardware"
    LACE_TRIM = "lace_trim"
    PATCHWORK = "patchwork"
    PEARL = "pearl"
    PIPING = "piping"
    POCKETS = "pockets"
    RHINESTONE = "rhinestone"
    SEQUINS = "sequins"
    SILVER_TONE_HARDWARE = "silver_tone_hardware"
    STUD = "stud"
    TASSEL = "tassel"
    ZIPPER = "zipper"


class StyleTraitValue(StrEnum):
    BOHEMIAN = "bohemian"
    BOLD = "bold"
    CASUAL = "casual"
    CLASSIC = "classic"
    DELICATE = "delicate"
    EDGY = "edgy"
    ELEGANT = "elegant"
    FEMININE = "feminine"
    FORMAL = "formal"
    GLAMOROUS = "glamorous"
    MINIMAL = "minimal"
    MODERN = "modern"
    PLAYFUL = "playful"
    POLISHED = "polished"
    PREPPY = "preppy"
    RELAXED = "relaxed"
    ROMANTIC = "romantic"
    RUGGED = "rugged"
    SMART_CASUAL = "smart_casual"
    SOPHISTICATED = "sophisticated"
    SPORTY = "sporty"
    STREETWEAR = "streetwear"
    UTILITARIAN = "utilitarian"
    VINTAGE = "vintage"
    WHIMSICAL = "whimsical"


class AestheticSignalValue(StrEnum):
    COTTAGECORE = "cottagecore"
    DARK_ACADEMIA = "dark_academia"
    MINIMALIST = "minimalist"
    PREPPY = "preppy"
    SOFT_FEMININE = "soft_feminine"
    STREETWEAR = "streetwear"
    VINTAGE_INSPIRED = "vintage_inspired"


class ImageQualityWarning(StrEnum):
    BLURRY = "blurry"
    DARK = "dark"
    EXCESSIVE_BACKGROUND_CLUTTER = "excessive_background_clutter"
    MULTIPLE_PROMINENT_ITEMS = "multiple_prominent_items"
    NO_CLEAR_PRIMARY_ITEM = "no_clear_primary_item"
    OCCLUDED = "occluded"


class MatchClassification(StrEnum):
    STRONG_FIT = "STRONG_FIT"
    MODERATE_FIT = "MODERATE_FIT"
    INTENTIONAL_CONTRAST = "INTENTIONAL_CONTRAST"
    WEAK_FIT = "WEAK_FIT"
    UNCERTAIN = "UNCERTAIN"


class MatchDimension(StrEnum):
    COLOUR = "colour"
    STYLE = "style"
    PATTERN_MATERIAL = "pattern_material"
    SHAPE_DETAIL = "shape_detail"
    SEMANTIC_EMBEDDING = "semantic_embedding"


class FeedbackCategory(StrEnum):
    TASTE = "TASTE"
    DECISION = "DECISION"


class FeedbackType(StrEnum):
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"
    BOUGHT = "BOUGHT"
    NOT_BOUGHT = "NOT_BOUGHT"


Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
Proportion = Annotated[float, Field(gt=0.0, le=1.0)]
Score = Annotated[float, Field(ge=0.0, le=1.0)]
Weight = Annotated[float, Field(gt=0.0, le=1.0)]


class ItemTypeObservation(DomainModel):
    value: Annotated[str, Field(min_length=1, max_length=80)]
    confidence: Confidence


class ColourObservation(DomainModel):
    name: Annotated[str, Field(min_length=1, max_length=50)]
    hex: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    proportion: Proportion
    confidence: Confidence


class PatternObservation(DomainModel):
    value: PatternValue
    confidence: Confidence


class MaterialObservation(DomainModel):
    value: MaterialValue
    confidence: Confidence


class TextureObservation(DomainModel):
    value: TextureValue
    confidence: Confidence


class ShapeTraitObservation(DomainModel):
    value: ShapeTraitValue
    confidence: Confidence


class DecorativeDetailObservation(DomainModel):
    value: DecorativeDetailValue
    confidence: Confidence


class StyleTraitObservation(DomainModel):
    value: StyleTraitValue
    confidence: Confidence


class AestheticSignalObservation(DomainModel):
    value: AestheticSignalValue
    confidence: Confidence


class ImageQuality(DomainModel):
    usable: bool
    score: Score
    warnings: list[ImageQualityWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def ensure_warnings_match_usability(self) -> ImageQuality:
        unusable_warnings = {
            ImageQualityWarning.MULTIPLE_PROMINENT_ITEMS,
            ImageQualityWarning.NO_CLEAR_PRIMARY_ITEM,
        }
        if self.usable and any(warning in unusable_warnings for warning in self.warnings):
            raise ValueError("unusable image warnings require usable=false")
        return self


class ItemVisualFeaturesV1(DomainModel):
    """Validated, explainable visual evidence extracted from one item image."""

    schema_version: Literal[1] = Field(default=1, alias="schemaVersion")
    item_type: ItemTypeObservation = Field(alias="itemType")
    item_name: Annotated[str, Field(min_length=1, max_length=120)] = Field(
        alias="itemName"
    )
    colours: list[ColourObservation] = Field(default_factory=list, max_length=8)
    patterns: list[PatternObservation] = Field(default_factory=list, max_length=5)
    materials: list[MaterialObservation] = Field(default_factory=list, max_length=5)
    textures: list[TextureObservation] = Field(default_factory=list, max_length=5)
    shape_traits: list[ShapeTraitObservation] = Field(
        default_factory=list,
        max_length=5,
        alias="shapeTraits",
    )
    decorative_details: list[DecorativeDetailObservation] = Field(
        default_factory=list,
        max_length=5,
        alias="decorativeDetails",
    )
    style_traits: list[StyleTraitObservation] = Field(
        default_factory=list,
        max_length=6,
        alias="styleTraits",
    )
    aesthetic_signals: list[AestheticSignalObservation] = Field(
        default_factory=list,
        max_length=4,
        alias="aestheticSignals",
    )
    quality: ImageQuality
    observations: list[Annotated[str, Field(min_length=1, max_length=240)]] = Field(
        default_factory=list,
        max_length=5,
    )
    description: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def validate_colour_proportions(self) -> ItemVisualFeaturesV1:
        if not self.quality.usable:
            return self

        if not self.colours:
            raise ValueError("usable images require at least one colour")

        total_proportion = sum(colour.proportion for colour in self.colours)
        if not 0.9 <= total_proportion <= 1.1:
            raise ValueError("colour proportions must sum to approximately 1.0")
        return self


class WeightedFeature(DomainModel):
    value: Annotated[str, Field(min_length=1, max_length=80)]
    weight: Weight


class WeightedColour(DomainModel):
    name: Annotated[str, Field(min_length=1, max_length=50)]
    hex: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    weight: Weight


class SemanticEmbedding(DomainModel):
    provider: Annotated[str, Field(min_length=1, max_length=80)]
    model: Annotated[str, Field(min_length=1, max_length=120)]
    dimensions: Annotated[int, Field(gt=0)]
    input_type: Literal["canonical_visual_features"] = "canonical_visual_features"
    schema_version: Annotated[int, Field(gt=0)]
    values: list[float] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dimensions(self) -> SemanticEmbedding:
        if len(self.values) != self.dimensions:
            raise ValueError("embedding value count must match dimensions")
        return self


class AestheticProfileV1(DomainModel):
    """Immutable, multidimensional snapshot built from owned-item features."""

    schema_version: Literal[1] = Field(default=1, alias="schemaVersion")
    user_id: UUID = Field(alias="userId")
    colours: list[WeightedColour] = Field(min_length=1)
    patterns: list[WeightedFeature] = Field(default_factory=list)
    materials: list[WeightedFeature] = Field(default_factory=list)
    textures: list[WeightedFeature] = Field(default_factory=list)
    shape_traits: list[WeightedFeature] = Field(
        default_factory=list,
        alias="shapeTraits",
    )
    decorative_details: list[WeightedFeature] = Field(
        default_factory=list,
        alias="decorativeDetails",
    )
    style_traits: list[WeightedFeature] = Field(
        default_factory=list,
        alias="styleTraits",
    )
    aesthetic_signals: list[WeightedFeature] = Field(
        default_factory=list,
        alias="aestheticSignals",
    )
    embedding_centroid: SemanticEmbedding = Field(alias="embeddingCentroid")
    colour_diversity: Score = Field(alias="colourDiversity")
    style_diversity: Score = Field(alias="styleDiversity")
    contributing_feature_ids: list[UUID] = Field(
        min_length=5,
        alias="contributingFeatureIds",
    )
    summary: Annotated[str, Field(min_length=1, max_length=500)]
    algorithm_version: Annotated[int, Field(gt=0)] = Field(
        alias="algorithmVersion"
    )


class MatchEvidence(DomainModel):
    dimension: MatchDimension
    candidate_values: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(
        min_length=1,
        alias="candidateValues",
    )
    profile_values: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(
        min_length=1,
        alias="profileValues",
    )
    statement: Annotated[str, Field(min_length=1, max_length=280)]
    confidence: Confidence


class MatchComponentScore(DomainModel):
    dimension: MatchDimension
    score: Score
    effective_weight: Weight = Field(alias="effectiveWeight")
    confidence: Confidence


class MatchResultV1(DomainModel):
    """Explainable deterministic comparison of a candidate and profile snapshot."""

    schema_version: Literal[1] = Field(default=1, alias="schemaVersion")
    candidate_item_id: UUID = Field(alias="candidateItemId")
    profile_id: UUID = Field(alias="profileId")
    overall_score: Score = Field(alias="overallScore")
    classification: MatchClassification
    component_scores: list[MatchComponentScore] = Field(
        min_length=1,
        alias="componentScores",
    )
    matching_evidence: list[MatchEvidence] = Field(
        default_factory=list,
        alias="matchingEvidence",
    )
    contrasting_evidence: list[MatchEvidence] = Field(
        default_factory=list,
        alias="contrastingEvidence",
    )
    explanation: Annotated[str, Field(min_length=1, max_length=700)]
    scoring_version: Annotated[int, Field(gt=0)] = Field(
        alias="scoringVersion"
    )
    explanation_version: Annotated[int, Field(gt=0)] = Field(
        alias="explanationVersion"
    )

    @model_validator(mode="after")
    def validate_component_weights(self) -> MatchResultV1:
        effective_weight_total = sum(
            component.effective_weight for component in self.component_scores
        )
        if not 0.99 <= effective_weight_total <= 1.01:
            raise ValueError("effective component weights must sum to 1.0")
        return self
