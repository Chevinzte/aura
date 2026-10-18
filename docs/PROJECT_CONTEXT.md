# AURA Project Context

## Status

AURA's local MVP is implemented.

Release completion, remaining V1 production work, and the V2 backlog are tracked
in `docs/ROADMAP.md`. That file is the durable handoff when chat history is not
available.

The current system can:

- collect belongings a user confirms they like;
- extract structured visual features from each belonging;
- build a multidimensional aesthetic profile after five usable owned items;
- compare a candidate item with the active profile;
- return an explainable, subjective compatibility assessment;
- capture taste and purchase-decision feedback;
- display, update, and reset the user's profile through Telegram;
- apply an optional user-selected fashion presentation to generated suggestions;
- generate item-specific suggestion rationales with varied controlled contrasts;
- produce item-specific version 5 match explanations without changing scoring;
- show a richer evidence-based profile summary without repeating every displayed trait;
- propagate non-secret request references for operational failure diagnosis;
- browse uploaded belongings with their retained private images;
- apply confirmed, versioned corrections to selected owned-item feature fields;
- reanalyze a selected owned item with explicit cost, preview, and save confirmations.

The FastAPI backend, Telegram client, Supabase schema, storage integration, AI
adapters, deterministic profile aggregation, matching logic, and automated tests
are implemented. Deployment is not yet decided.

## Product

AURA is an AI-powered aesthetic matcher that learns from belongings a user likes
and evaluates how a new item may fit or intentionally contrast with their
personal style.

The core question is:

> Does this item fit my aesthetic?

AURA is an Aesthetic Matcher. Aesthetic discovery supports onboarding, but AURA
must not force a user into one rigid label such as "coquette" or "minimalist."
The user's aesthetic is represented as a combination of visual preferences.

## Architecture

```text
Telegram Bot
     |
     v
FastAPI Backend ----> Supabase PostgreSQL + Storage
     |
     +----> AI Lodge OpenAI-compatible API
     |
     `----> OpenAI Images API
```

Telegram is a frontend adapter only. It must not contain prompts, profile
aggregation, scoring, persistence, or provider-specific AI logic. Business logic
belongs in the FastAPI application layer so a web or mobile client can be added
without rewriting the core system.

## Technology Stack

- Language: Python 3.12+
- Backend: FastAPI
- MVP client: Telegram Bot API using long polling
- Database: Supabase PostgreSQL
- Vector storage: pgvector in Supabase PostgreSQL
- Image storage: private Supabase Storage bucket
- MVP identity: Telegram user ID
- AI gateway: AI Lodge through an OpenAI-compatible API
- Vision model: `gemini-3.5-flash-lite`
- Embedding model: `text-embedding-3-small`
- Embedding dimensions: 1536
- Optional reference-image provider: OpenAI Images API
- Reference-image model: environment-configured, initially `gpt-image-2.5-flare`
- Deployment: not decided

Model identifiers and provider connection details are environment configuration.
AI providers must remain replaceable behind provider-neutral interfaces.

## Repository Structure

```text
aura/
|-- backend/                 FastAPI API and core business logic
|-- telegram-bot/            Telegram frontend adapter
|-- supabase/migrations/     PostgreSQL schema and database functions
|-- docs/                    Architecture and product decisions
|-- ai/                      AI-related project area
|-- .env.example             Required configuration names
|-- restart-aura.ps1         Combined local service launcher
`-- README.md                Setup and usage instructions
```

## MVP Telegram Flow

1. The user starts AURA through Telegram.
2. The user uses `/add` to upload belongings they genuinely like, either individually
   or as a Telegram album of up to ten different items.
3. AURA validates each image, extracts visual features, and creates a semantic
   feature embedding.
4. Upload responses show progress toward the five-item minimum.
5. AURA builds or rebuilds the user's profile automatically.
6. The user can inspect the profile with `/profile`.
7. The user uses `/check` to evaluate an owned or prospective item.
8. AURA returns a classification with matching and contrasting evidence.
9. Telegram asks two separately labeled questions: whether the item suits the
   user's taste and what purchase decision they made.
10. The user can use `/wardrobe` or `/resetprofile` to change profile inputs.

Current commands:

- `/start`: show primary actions;
- `/add`: enter owned-item upload mode and accept one photo or an album of up to ten
  different items, with one primary item per photo and optional captions;
- `/check`: enter candidate comparison mode;
- `/profile`: display the current profile or collection progress;
- `/suggestion`: generate non-commercial wardrobe-building reference items from a
  ready profile, with up to five AI-generated images per interaction;
- `/settings`: choose Menswear, Womenswear, Gender-neutral, or No preference for
  generated clothing ideas;
- `/wardrobe`: browse owned belongings ten per page, view the stored image and
  effective analysis, correct one guided field, reanalyze with confirmation, or
  remove the item;
- `/resetprofile`: confirm removal of all owned profile inputs;
- `/help`: display command and image guidance;
- `/done`: leave the current upload mode.

The Telegram command menu is refreshed automatically when the bot starts.

## Manual Acceptance Status

The local Telegram flow has been manually verified for:

- `/add` with individual photos and albums of 5, 10, and 12 photos; Telegram
  delivers albums larger than ten as separate media groups, and AURA processes
  each received group;
- `/profile` generation and display after reaching the five-item minimum;
- `/check` classification, structured evidence, and feedback actions for Fits my
  taste, Not my taste, Bought it, and Passed on it;
- `/suggestion` intent and category selection, generated reference images, and
  the optional two-more flow;
- `/wardrobe` browsing, guided item editing, removal confirmation, profile
  rebuilding, and navigation beyond the first ten owned items;
- `/resetprofile` confirmation, owned-item clearing, and progress reset.

These checks establish that the local MVP works end to end with the configured
Supabase, AI Lodge, OpenAI Images, and Telegram services. They do not replace
production security, deployment, monitoring, or broader quality evaluation.

## AI Pipeline

The accepted MVP pipeline is defined in `docs/AI_PIPELINE.md`:

```text
Image
  -> image validation
  -> structured visual feature extraction
  -> canonical feature text
  -> semantic embedding
  -> owned-item profile aggregation
  -> deterministic candidate/profile comparison
  -> classification and evidence-grounded explanation
  -> feedback capture
```

Structured visual features are the primary explainable representation. The
embedding is a secondary semantic signal generated from canonical feature text;
it is not a native image embedding.

The vision model extracts observable evidence only. It must not build profiles,
calculate compatibility, choose the final classification, or write an
ungrounded recommendation.

## Wardrobe Suggestions

`/suggestion` is an optional profile-guided inspiration flow, not a shopping or
outfit-generation system. It requires a ready profile and lets the user choose a
safe extension, intentional contrast, or surprise direction, followed by Any
Category, Tops, Outerwear, Pants, Accessories, or Footwear. The backend uses the
complete active profile and owned item types to plan distinct single-item ideas
within that category, then asks a provider-neutral image generator for isolated
product-style reference images.

The first request generates three references. Telegram places fresh controls
below those images so the user can generate two more or finish the session. A
second batch brings the interaction maximum to five and ends the session. Images
must show one item only,
without people, outfits, brands, logos, text, or retailer claims. Suggestions do
not create owned or candidate items, mutate the profile, or influence matching.
Generated images are not persisted by AURA; after they are sent, they remain in
the Telegram conversation under Telegram's normal retention behavior.

AURA warns that a small or visually similar profile can produce similar ideas.
The backend stores only generated concept metadata, never the generated image or
raw prompt, so it can avoid recently shown concepts across sessions. Any Category
spreads selections across wardrobe categories, secondary profile traits rotate
between prompts, and Surprise Me allows a stronger controlled departure while
retaining one or two familiar profile anchors.

Before the first `/suggestion`, AURA asks the user to choose an optional fashion
presentation: Menswear, Womenswear, Gender-neutral, or No preference. The user
can change it through `/settings`. This preference is self-reported, is never
inferred from names or photos, and constrains suggestion catalog choices and
image prompts. It does not change visual feature extraction, profile aggregation,
or `/check` scoring. Body type is intentionally deferred until AURA supports
fit-focused or outfit guidance where that input would provide meaningful value.

## Wardrobe Browser and Corrections

`/wardrobe` is a private browser for active `OWNED` items, not a retailer catalogue
or outfit builder. It displays ten items per page. Opening an item retrieves the
exact retained upload from private Supabase Storage through the backend and shows
the effective structured analysis. Telegram never receives storage credentials or
a permanent public image URL.

Corrections use **Edit Item Details** and guided field editing. A user selects one
of Item Name, Item Type, Colours, Patterns, Materials, Textures, Style Traits,
Shape Traits, or Decorative Details. AURA shows the current effective value and
typed-input examples. Users may send comma-separated values; common synonyms,
item-type terms, and colour names are normalized by the backend. Description is
not editable. Unknown controlled values are rejected with close alternatives and
no data is changed.

The user reviews Current Value and New Value before saving. Back to Editable
Fields and Discard Changes preserve the item context without saving, while Back to
Item leaves editing. The original AI analysis remains immutable. Each confirmed
save creates a new correction version with corrected features, canonical text,
and a compatible semantic embedding. The active profile is then rebuilt from
effective corrected features. Profile snapshots record both the source analysis
and correction identifier for explainability. If rebuilding fails, AURA restores
the previously active correction.

**Reanalyze Item** is explicitly user-triggered and warns about AI cost before any
provider call. AURA analyzes the retained private image, displays a current-versus-
proposed preview, and requires Save New Analysis or Discard. Saving creates an
accepted `AI_REANALYSIS` feature revision, replaces any active manual correction,
and rebuilds the profile. Discarding changes nothing. The original analysis and
previous accepted revisions remain available for provenance and rollback.

## Item Visual Features V1

Each usable item can include:

- item type and inferred item name;
- colours with hex values, proportions, and confidence;
- patterns;
- materials;
- textures;
- shape traits;
- decorative details;
- style traits;
- supporting aesthetic signals;
- image quality and an evidence-based description;
- canonical feature text and its semantic embedding.

Provider output is schema-validated and normalized into controlled fields.
Unknown but useful observations may be retained without silently changing the
controlled vocabulary. Controlled-vocabulary revision 2 expands common fashion
patterns, materials, textures, shapes, decorative details, and style traits.
Existing images are not automatically reanalyzed; the expanded vocabulary applies
to new analyses and confirmed manual corrections.

## Aesthetic Profile V1

Only successfully analyzed `OWNED` items contribute to the profile. `CANDIDATE`
items never change the profile merely because they were checked.

The initial profile requires at least five usable owned items. The profile is
rebuilt deterministically when a contributing item is added, removed, or corrected.

The profile contains weighted distributions for colours, patterns, materials,
textures, shapes, decorative details, style traits, and aesthetic signals. It
also stores a normalized embedding centroid, colour and style diversity,
contributing feature identifiers, and a generated evidence-based summary.

The user-facing `/profile` response exposes only display-safe leading traits and
the summary. It does not expose embeddings, weights, internal identifiers, or
model metadata.

## Candidate Matching

Candidate matching combines deterministic components for:

- colour compatibility;
- style-trait compatibility;
- pattern and material compatibility;
- shape and decorative-detail compatibility;
- semantic feature-embedding similarity.

Internal numerical scores support consistent classification but are not
presented as objective truth. User-facing classifications are:

- Strong Fit
- Moderate Fit
- Intentional Contrast
- Weak Fit
- Uncertain

The `/check` explanation format is:

```text
Classification: [result]

Matching Evidence: [up to two grounded similarities]

Contrasting Evidence: [meaningful contrast or limited-overlap evidence]

Subjective Qualifier: Based on your uploaded items, this is subjective guidance rather than a rule.
```

Explanation version 5 names the analyzed item, uses natural dimension-specific
phrasing, clarifies when similarity comes from the combined semantic signal, and
provides clearer wording for limited evidence and absent contrasts. Matching scores,
thresholds, and classification rules remain on scoring version 1.

## Feedback

Telegram presents feedback as two independent labeled questions. **Does this item
suit your taste?** captures `LIKE` or `DISLIKE`. **What did you decide?** captures
`BOUGHT` or `NOT_BOUGHT`; users may return to the decision buttons later. After a
choice is saved, Telegram replaces that question and its buttons with a persistent
**Feedback received** confirmation naming the recorded response. The other question
remains available until it is answered.

Supported feedback values are:

- `LIKE`
- `DISLIKE`
- `BOUGHT`
- `NOT_BOUGHT`

Feedback is persisted and associated with the completed match. MVP V1 does not
automatically change profile features, weights, thresholds, or scoring from this
feedback. Learning from feedback is a later, explicitly designed feature.

## Profile Management and Retention

Item removal through `/wardrobe` and profile resets through `/resetprofile`
require explicit Telegram confirmation.

Removing owned items:

- lists active owned items newest-first with ten-item Telegram pages;
- verifies ownership in the backend;
- soft-deletes only `OWNED` items;
- deactivates the previous profile atomically;
- rebuilds the profile when at least five usable owned items remain;
- preserves candidate items, matches, feedback, historical analyses, immutable
  profile snapshots, and retained images.

Full account and storage deletion is a separate future backend workflow.

## Security Boundary

Supabase server-side credentials and AI provider credentials belong only in the
FastAPI runtime. Telegram and future clients must never access Supabase directly
or receive server-side secrets.

Telegram user ID is sufficient identity for the local MVP. Before exposing the
backend publicly, requests from the Telegram service must be authenticated with
an internal shared secret or equivalent private service boundary. Plain
`X-Telegram-User-Id` headers must not be trusted from the public internet.

Do not introduce Supabase Auth unless a future client requires it and the change
is discussed explicitly.

## Product Principles

1. Personal aesthetic is subjective.
2. Do not treat compatibility as objective truth.
3. Explain why an item matches or contrasts.
4. Do not collapse a user into one aesthetic label.
5. Allow intentional contrast.
6. Keep Telegram separate from core business logic.
7. Keep AI providers replaceable.
8. Preserve versioned evidence and profile provenance.
9. Do not let candidate checks silently alter the profile.
10. Require confirmation for destructive profile actions.

## Out of Scope for Initial MVP

Do not initially build:

- a product recommendation marketplace;
- shopping catalogue or retailer integrations;
- web scraping;
- outfit generation;
- a full digital wardrobe;
- a complex learned recommendation system;
- a web or mobile frontend;
- automatic profile learning from feedback;
- Supabase Auth without a frontend requirement.

## Current Priorities

The local MVP feature set and V2.1-V2.2 product features are complete. V2.2
wardrobe browsing and guided editing have been manually verified, and initial
test users report that the application works. General user-experience feedback
is recorded for a later improvement pass.

The following production tasks are intentionally reserved for immediately before
submission:

1. authenticating Telegram-to-backend requests before public deployment;
2. adding rate limits and AI-provider cost controls;
3. configuring monitoring and actionable production error reporting;
4. verifying Supabase database and private-storage backups;
5. selecting hosting, configuring production secrets, and preparing deployment
   and recovery instructions.

Before that final stage, prioritize reviewing the collected user feedback and
agreeing on the next user-experience improvements. The latest improvement pass
added a repetition disclaimer and cross-session suggestion diversity. Broader
classification and explanation evaluation remains desirable if the submission
schedule permits.

The detailed checklists, completed V2 scope, deferred learning work, and accepted
session decisions are maintained in `docs/ROADMAP.md`.

Do not add major technologies, database entities, AI models, scoring changes, or
deployment architecture implicitly. Update the relevant design document and
discuss the change first.
