# AURA AI Pipeline

## Status

Accepted MVP design.

This document defines the AI pipeline contract for AURA's MVP. Implementation
changes that alter the models, feature schema, embedding input, profile
aggregation, matching weights, classifications, or explanation strategy should
update this document and increment the affected version identifier.

## Goals

The pipeline learns a multidimensional representation of a user's aesthetic
from belongings they confirm they like, then evaluates a candidate item against
that representation.

The pipeline must:

- represent preferences as a combination of visual characteristics;
- explain which characteristics match, contrast, or remain uncertain;
- treat compatibility as subjective guidance rather than objective truth;
- recognize intentional contrast;
- keep AI providers replaceable;
- remain independent of Telegram and other frontend clients.

The pipeline does not provide product recommendations, generate outfits, scrape
retailers, or maintain a complete digital wardrobe.

## Pipeline Overview

```text
Image
  -> input and image-quality validation
  -> structured visual feature extraction
  -> canonical feature text generation
  -> semantic embedding generation
  -> owned-item profile aggregation
  -> candidate/profile comparison
  -> result classification
  -> evidence-grounded explanation
  -> feedback capture
```

The structured features are the primary, explainable representation. The
embedding is a secondary semantic signal derived from those features. It is not
a native image embedding.

## Model Decisions

### Vision

- Provider-facing model identifier: `gemini-3.5-flash-lite`
- Input: one item image and the extraction instructions
- Output: schema-constrained JSON
- Temperature: low
- Purpose: extract observable visual evidence only

The vision model must not build profiles, calculate compatibility, assign a
match classification, or generate the final recommendation.

### Embeddings

- Provider-facing model identifier: `text-embedding-3-small`
- Input: deterministic canonical text generated from validated features
- Dimensions: 1536
- Similarity measure: cosine similarity
- Purpose: provide a secondary semantic similarity signal

The model does not accept images. AURA must describe this representation as a
semantic feature embedding, not a direct visual embedding.

### Configuration

Model identifiers and provider connection details must be configuration, not
hard-coded domain constants. Initial environment settings are:

```text
AURA_VISION_MODEL=gemini-3.5-flash-lite
AURA_EMBEDDING_MODEL=text-embedding-3-small
AURA_EMBEDDING_DIMENSIONS=1536
```

The application must access each capability through a provider-neutral
interface so a model or provider can be replaced without changing profile or
matching logic.

## Item Visual Features V1

`ItemVisualFeaturesV1` is the contract between feature extraction, persistence,
embedding generation, profile aggregation, matching, and explanations.

The implementation should use Pydantic models and JSON Schema to validate the
following conceptual structure:

```json
{
  "schemaVersion": 1,
  "itemType": {
    "value": "handbag",
    "confidence": 0.97
  },
  "itemName": "small floral handbag",
  "colours": [
    {
      "name": "blush pink",
      "hex": "#D9A6AA",
      "proportion": 0.55,
      "confidence": 0.91
    }
  ],
  "patterns": [
    {
      "value": "floral",
      "confidence": 0.93
    }
  ],
  "materials": [
    {
      "value": "leather",
      "confidence": 0.72
    }
  ],
  "textures": [
    {
      "value": "smooth",
      "confidence": 0.78
    }
  ],
  "shapeTraits": [
    {
      "value": "rounded",
      "confidence": 0.84
    }
  ],
  "decorativeDetails": [
    {
      "value": "gold-tone hardware",
      "confidence": 0.88
    }
  ],
  "styleTraits": [
    {
      "value": "delicate",
      "confidence": 0.86
    }
  ],
  "aestheticSignals": [
    {
      "value": "soft feminine",
      "confidence": 0.76
    }
  ],
  "quality": {
    "usable": true,
    "score": 0.9,
    "warnings": []
  },
  "observations": [],
  "description": "A compact blush pink handbag with floral details and gold-tone hardware."
}
```

### Schema Rules

- Colours contain a normalized name, approximate hex value, proportion, and
  confidence.
- Colour proportions should approximately sum to 1.0; minor rounding variance
  is permitted.
- Patterns, materials, textures, shape traits, decorative details, style traits,
  and aesthetic signals use controlled vocabularies.
- Aesthetic signals are supporting metadata and must not replace concrete visual
  features.
- Confidence values range from 0.0 to 1.0.
- Free text is limited to the item name, observations, and neutral description.
- The extractor uses `unknown` or an empty collection when evidence is
  insufficient. It must not guess.
- The description must be factual and contain no compatibility judgment.
- The implementation must preserve unknown controlled-vocabulary values in
  observations for later vocabulary review rather than silently inventing a new
  canonical value.

The exact controlled-vocabulary values will be defined with the Pydantic schema.
Vocabulary changes that affect canonical embedding text require a new embedding
schema version.

## Image Acceptance

Before an AI request, the backend validates:

- supported MIME type;
- configured file-size limit;
- successful image decoding;
- configured minimum dimensions;
- image orientation normalization.

The vision extractor reports quality warnings for blur, darkness, severe
occlusion, excessive background clutter, and other conditions that reduce
confidence.

An image is not usable when:

- it contains no identifiable primary item;
- several items are equally prominent;
- the item is too obscured or blurred for meaningful analysis;
- the content cannot be processed safely or reliably.

The backend returns a recoverable result explaining how the user can retake the
image. Frontend-specific wording belongs to the client layer.

## Canonical Embedding Text V1

Embedding input is generated by application code, never by another free-form AI
request. Values are lowercase, normalized, deduplicated, and emitted in a fixed
field order.

```text
item_type: handbag
colours: blush pink, cream
patterns: floral
materials: leather, gold metal
textures: smooth
shape_traits: compact, rounded
decorative_details: gold-tone hardware
style_traits: delicate, romantic, soft
aesthetic_signals: soft feminine
```

Canonical text excludes:

- free-text item names;
- generated descriptions;
- confidence numbers;
- image-quality warnings;
- speculative observations;
- profile or compatibility information.

The persisted embedding metadata must contain:

```json
{
  "provider": "configured-provider",
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "inputType": "canonical_visual_features",
  "embeddingSchemaVersion": 1
}
```

Embeddings from different models, dimensions, or embedding schema versions must
never be compared. The canonical text should be retained so embeddings can be
audited or regenerated without rerunning vision extraction.

## Aesthetic Profile V1

Only successfully analyzed `OWNED` items that the user confirms they like
contribute to the profile. `CANDIDATE` items never affect the profile merely
because they were evaluated.

The initial profile requires at least five usable owned items. A profile is
rebuilt deterministically whenever a contributing owned item is added, removed,
reprocessed, or corrected.

Removing an owned item soft-deletes it from future profile inputs and
deactivates the previous profile before rebuilding. Resetting a profile applies
the same exclusion to all owned items. Historical analyses and immutable profile
snapshots remain available for explainability; candidate items and feedback are
not deleted.

The profile contains:

- weighted colour distribution;
- weighted pattern distribution;
- weighted material distribution;
- weighted texture distribution;
- weighted shape and decorative-detail distributions;
- weighted style-trait distribution;
- supporting aesthetic-signal distribution;
- normalized embedding centroid;
- colour diversity;
- style diversity;
- contributing item identifiers;
- generated summary derived from aggregated evidence;
- model and schema version metadata.

### Aggregation Rules

- Each feature contribution is weighted by extraction confidence.
- Colour contribution is additionally weighted by its estimated image
  proportion.
- Each item begins with equal influence on the profile.
- Duplicate or near-duplicate items have reduced influence so repeated uploads
  do not dominate the profile.
- Low-confidence values contribute less rather than being treated as equally
  reliable.
- The profile keeps distributions instead of collapsing the user into one
  aesthetic label.
- The embedding centroid is the normalized mean of compatible owned-item
  embeddings.
- Diversity is measured separately for colour and style and is used when
  evaluating intentional contrast.

### Guided Feature Corrections

Owned-item corrections are user-confirmed overlays, not edits to the original AI
analysis. A correction changes one guided field per interaction, is validated by
the same `ItemVisualFeaturesV1` contract, and is previewed before persistence.
Users type natural values, separating multiple values with commas. The backend
normalizes casing, spacing, common synonyms, and common item-type terms. Colour
names are mapped to standard hex values, so users do not need to provide hex
codes. Unknown controlled values are rejected with close accepted alternatives;
they are never silently added to profile data. Description remains read-only.

Saving a correction generates canonical embedding text and a fresh semantic
embedding from the complete corrected feature object. The correction is compatible
only with its recorded feature and embedding schema versions. Profile aggregation
uses the active correction when compatible and otherwise uses the original
analysis. Every resulting profile contribution records both the source feature ID
and optional correction ID. The previous correction is restored if profile
rebuilding fails.

### User-Triggered Reanalysis

Reanalysis is available only from a selected owned item in `/wardrobe`; AURA never
automatically reprocesses historical images. Before invoking the provider, Telegram
warns that the action consumes AI credits and may produce different output. The
backend downloads the retained private image, validates it again, and runs the same
versioned vision, canonical-text, and embedding pipeline used for new items.

The proposed result is stored as an inactive `AI_REANALYSIS` feature revision and
shown beside the current effective analysis. It does not affect the profile until
the user selects **Save New Analysis**. Confirmation atomically activates the new
revision, deactivates any previous manual correction or reanalysis, and rebuilds
the profile. A failed rebuild restores the previous active revision. Discarding
deletes the inactive preview. Original AI features and inactive accepted revisions
remain preserved for provenance.

## Candidate Matching V1

Matching is deterministic and operates on a candidate's validated visual
features, its semantic embedding, and the current profile snapshot.

### Components

| Component | Weight |
| --- | ---: |
| Colour compatibility | 30% |
| Style-trait compatibility | 25% |
| Pattern and material compatibility | 15% |
| Shape and decorative-detail compatibility | 10% |
| Semantic embedding similarity | 20% |

Component weights are configuration belonging to scoring version 1. The
embedding remains secondary because it is derived from the same structured
features used by the explicit components.

### Scoring Rules

- Each component produces a normalized internal score from 0.0 to 1.0.
- Each component also returns positive evidence, contrasting evidence, and an
  evidence-confidence value.
- Low-confidence evidence reduces that component's effective influence.
- Missing evidence redistributes influence across supported components rather
  than automatically counting as incompatibility.
- Every analysis stores the component scores, effective weights, evidence, and
  scoring version.
- Internal scores support consistent classification but must not be presented as
  objective scientific measurements.

Scoring version 1 calculates components as follows:

- colour compatibility uses normalized RGB distance between candidate and
  profile colours, weighted by candidate proportion, extraction confidence, and
  profile prominence;
- style, pattern, material, shape, and decorative-detail compatibility use
  exact controlled-vocabulary overlap, weighted by extraction confidence and
  profile prominence;
- semantic compatibility uses cosine similarity clamped to the 0.0 through 1.0
  range;
- candidate image quality caps each component's evidence confidence;
- each configured component weight is multiplied by evidence confidence, then
  the supported component weights are renormalized to sum to 1.0.

Scoring version 1 treats component scores of at least 0.72 as strong matching
evidence and scores of at most 0.35 as major differences for intentional
contrast detection. The relevant profile diversity must be at least 0.45. A
result is `UNCERTAIN` when fewer than two components have confidence of at least
0.35.

### Classifications

Initial configurable thresholds are:

- `STRONG_FIT`: adjusted overall score greater than or equal to 0.78;
- `MODERATE_FIT`: adjusted overall score from 0.58 through 0.77;
- `WEAK_FIT`: adjusted overall score below 0.58;
- `UNCERTAIN`: inadequate image quality or insufficient confident evidence;
- `INTENTIONAL_CONTRAST`: assigned by the contrast rules instead of the normal
  score bands.

Threshold boundaries must be implemented without gaps and stored as part of
scoring version 1.

### Intentional Contrast

`INTENTIONAL_CONTRAST` requires all of the following:

- strong compatibility in at least two scored dimensions;
- a major difference in exactly one principal dimension;
- no major conflict across multiple dimensions;
- sufficient profile diversity or complementary evidence to support the
  difference;
- sufficient confidence in both the matching and contrasting evidence.

A medium overall score alone does not imply intentional contrast. The analysis
must identify the contrasting dimension and the features that make the rest of
the item coherent with the profile.

## Explanation V5

MVP explanations are deterministic templates populated only from stored match
evidence. They do not require another generative-model call.

Version 2 prioritizes concrete visual evidence over embedding terminology,
uses category-aware wording, and requires weak-fit explanations to describe
limited overlap rather than presenting only positive evidence.

Version 3 presents every explanation as four labeled sections separated by
blank lines: Classification, Matching Evidence, Contrasting Evidence, and
Subjective Qualifier.

Version 4 retains those sections while naming the analyzed item, using
dimension-specific wording, removing repetitive feature phrases, and explaining
uncertainty or the absence of a major contrast more directly. It changes only
the explanation template; scoring version 1 and its classifications are unchanged.

Version 5 makes dimension wording more natural and explicitly describes semantic
evidence as similarity in the combined visual-feature signal when no single listed
trait fully explains it. It still changes only the explanation template.

Each explanation contains:

- one user-facing classification;
- up to two important matching observations;
- up to one meaningful contrast observation;
- a subjective qualifier that avoids presenting the result as fact.

Example:

```text
Classification: Moderate Fit

Matching Evidence: This navy jacket uses structured styling, which also appears in your profile.

Contrasting Evidence: This navy jacket uses a navy palette that introduces a clear colour contrast with your profile.

Subjective Qualifier: Based on your uploaded items, this is subjective guidance rather than a rule.
```

Explanations must:

- use only evidence calculated by the matching service;
- prioritize concrete features over aesthetic labels;
- avoid unsupported claims and invented observations;
- avoid exposing internal numerical scores in the default user response;
- use language such as "appears," "may," and "based on your uploaded items."

## Feedback V1

The MVP records:

- `LIKE`: the candidate suits the user's taste;
- `DISLIKE`: the candidate does not suit the user's taste;
- `BOUGHT`: the user eventually acquired the candidate;
- `NOT_BOUGHT`: the user chose not to acquire the candidate.

Feedback is stored for evaluation and future learning. It does not automatically
change profile features, profile weights, match thresholds, or scoring weights
in MVP version 1.

## Failure Handling

### Provider Failures

- Apply configured request timeouts.
- Retry transient provider and network failures at most twice using exponential
  backoff.
- Do not retry permanent authentication, quota, or invalid-request failures.
- Record provider error categories without logging user images or secrets.

### Invalid Model Output

- Validate all structured output with `ItemVisualFeaturesV1`.
- Make one repair or re-extraction attempt after invalid output.
- Mark analysis as failed if the second response is invalid.
- Do not generate an embedding or update a profile from invalid features.

### Partial Pipeline Failures

- Persist stage status so failed work can be retried safely.
- Make processing idempotent for an item and pipeline version.
- Do not publish a match result until all required stages succeed.
- Return stable backend error codes that any frontend can translate into
  appropriate user messaging.
- Propagate a non-secret request reference from Telegram through the backend and
  include it in operational failure messages so logs can be correlated without
  exposing user data.

## Persistence Contract

The MVP uses the domain entities proposed in `PROJECT_CONTEXT.md`:

- users;
- items;
- item visual features;
- item feature corrections;
- aesthetic profiles;
- match analyses;
- feedback.

Structured features, profile distributions, and comparison evidence should use
PostgreSQL `JSONB` where their internal shape is governed by the versioned
application schema. Embeddings use pgvector with 1536 dimensions. Images use
private Supabase Storage, and the database stores the storage path rather than a
permanent public URL.

Every AI-generated record must include the applicable metadata:

- provider;
- model identifier;
- prompt version;
- feature schema version;
- embedding schema version;
- scoring version;
- creation timestamp.

Raw hidden reasoning must never be requested or stored. Retaining raw provider
responses is optional for development diagnostics and must be disabled or
redacted for production unless a separate privacy decision explicitly permits
it.

## Service Boundaries

The AI and matching capabilities expose provider-neutral operations equivalent
to:

```python
analyse_item(image) -> ItemVisualFeaturesV1
build_embedding(features) -> SemanticEmbedding
build_profile(owned_items) -> AestheticProfileV1
compare_item(candidate, profile) -> MatchResultV1
explain_match(match_result) -> ExplanationV1
generate_reference_image(prompt) -> GeneratedImage
```

FastAPI application services orchestrate persistence and these operations.
FastAPI routes remain thin. Telegram uploads images, requests operations, and
displays results through the backend API; it contains no prompts, profile logic,
matching logic, or provider-specific code.

The profile-read contract exposes only display-safe profile information:
collection progress, the user's display name, leading visual preferences, the
generated summary, and the profile generation time. It must not expose feature
weights, embeddings, internal identifiers, or model metadata. Frontends may
format these fields but must not independently derive profile rankings.

## Profile-Guided Reference Images

Wardrobe suggestions are a separate optional branch after profile aggregation;
they do not modify the accepted item-analysis, embedding, profile, or matching
pipeline.

```text
Active AestheticProfileV1 + owned item types + user intent
  -> deterministic suggestion planning
  -> constrained single-item image prompt
  -> provider-neutral image generation
  -> transient backend response
  -> Telegram photo
```

Supported intents are safe extension, intentional contrast, and surprise. An
optional user-selected fashion presentation constrains clothing ideas to
Menswear, Womenswear, Gender-neutral, or No preference. It is never inferred and
does not influence profile aggregation or candidate matching. A second input
optionally restricts planning to Tops, Outerwear, Pants,
Accessories, or Footwear; Any Category preserves the unrestricted behavior. The
planner uses the whole active profile rather than an aesthetic label alone and
avoids owned item types where practical. Prompts require one isolated,
product-style item with no person, outfit, logo, brand, text, watermark, or
retailer claim.

The initial Telegram action requests three images and may request two more, with
a maximum of five per interaction. Each small batch is generated concurrently
while individual provider failures can still return partial success. AURA does
not persist generated images, create item records from them, or feed them into
the profile. Provider keys, models, output settings, and timeouts remain
server-side environment configuration.

## Evaluation Plan

Before declaring the MVP ready, create a private evaluation set of approximately
30 to 50 representative belongings and candidate items.

The evaluation must assess separately:

- image usability decisions;
- item-type extraction;
- colour extraction;
- pattern and material extraction;
- style-trait consistency;
- profile summaries;
- classification agreement with human judgment;
- intentional-contrast detection;
- explanation faithfulness and usefulness.

Run `gemini-3.5-flash-lite` and `gpt-5-mini` against the same feature extraction
cases. Change the default vision model only when a measured quality improvement
justifies its cost and latency.

Evaluation examples and expected outputs must not be embedded into production
prompts in a way that leaks user data or overfits the pipeline to the test set.

## Versioning and Migration

Current versions are:

```text
feature_schema_version=2
vision_prompt_version=1
embedding_schema_version=2
profile_algorithm_version=1
scoring_version=1
explanation_version=5
```

Increment the relevant version when a change can alter persisted output or its
meaning. Model, dimension, or embedding-schema changes require new embeddings.
Feature-schema or prompt changes may require vision reprocessing. Scoring changes
require recomputing match results when old and new results need to be compared.

Old and new representations may coexist during migration, but incompatible
embeddings or profile versions must never be compared directly.

Vocabulary revision 2 is additive: it expands accepted enum values without
changing canonical field order, vector dimensions, or the embedding model. Existing
feature rows, corrections, and profiles are promoted through a metadata-only
migration, including the stored centroid schema marker. Existing images and vectors
are not regenerated. New uploads and confirmed corrections can use the expanded
values.

## Future Native Image Embeddings

When a suitable image-embedding model becomes available through the configured
provider:

1. add a separate image-embedding field and version;
2. generate vectors from the original stored images;
3. retain semantic feature embeddings during evaluation;
4. compare both signals against human judgments and user feedback;
5. update scoring weights only through a new scoring version;
6. never overwrite or compare incompatible vectors.

Native image embeddings are an enhancement, not an MVP dependency.
