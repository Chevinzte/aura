# AURA Delivery Roadmap and Session Handoff

This document is the durable handoff for product decisions, completed work, and
remaining tasks. Update it whenever a feature is accepted, deferred, or changed
so progress does not depend on chat history.

Last updated: 2026-10-18

## Release Status

### V1: Local MVP Complete

Implemented and locally verified:

- `/add` for individual photos and Telegram albums, using one primary belonging
  per photo and processing up to ten photos in each Telegram media group;
- AI visual-feature extraction, canonical feature text, semantic embeddings,
  and deterministic profile aggregation after five usable owned items;
- `/profile` with the user's Telegram display name, collection progress, and
  formatted style-profile sections;
- `/check` with Classification, Matching Evidence, Contrasting Evidence, and
  Subjective Qualifier sections;
- feedback actions for Fits my taste, Not my taste, Bought it, and Passed on it;
- `/suggestion` with intent and category selection, three initial generated
  references, an optional two more, controls below the images, and Stop
  Generating;
- `/settings` for self-reported Menswear, Womenswear, Gender-neutral, or No
  preference presentation choices used only by suggestions;
- item removal through `/wardrobe`, with confirmation, cancellation, and pagination;
- `/resetprofile` with confirmation while retaining candidate checks and
  feedback history;
- private Supabase image storage, PostgreSQL/pgvector persistence, migrations,
  AI-provider adapters, and a combined local restart script.

V1 is working as a local MVP. It is not yet production-ready.

### V1: Completed Validation

- [x] Manually test the V2.2 `/wardrobe` and guided item-editing flows. Both are
  working as expected.
- [x] Collect initial feedback from test users. Users reported that AURA works,
  while identifying general user-experience improvements to address later.

### V1: Work Immediately Before Submission

These tasks are intentionally reserved for the final production-preparation
stage:

- [ ] Authenticate Telegram-to-backend requests before exposing the backend.
- [ ] Add per-user and provider-aware rate limits plus cost controls for vision,
  embeddings, and image generation.
- [ ] Configure production monitoring and actionable error reporting.
- [ ] Configure and verify Supabase database and private-storage backups.
- [ ] Select hosting for the FastAPI service and Telegram worker, configure
  production secrets, and prepare deployment and recovery instructions.

### V1: Remaining Quality Work

- [x] Add a short `/suggestion` disclaimer explaining that small or visually
  similar profiles may produce similar ideas, and that adding more varied owned
  items can broaden the profile evidence.
- [x] Improve suggestion diversity by remembering recent concepts, avoiding
  repetition across sessions, rotating secondary visual traits, varying catalog
  selection, and making **Surprise Me** more exploratory.
- [ ] Evaluate classifications and explanations on approximately 30-50
  representative owned and candidate images if the submission schedule permits.
- [ ] Review collected user feedback and implement the agreed user-experience
  improvements before final production preparation.

### User-Facing Template Audit Backlog

- [x] Make `/suggestion` rationales item-specific by referencing each concept's
  item type and selected colour, material, texture, shape, or detail variation.
  Rotate appropriate contrast colours instead of repeatedly selecting the first
  available fixed accent.
- [x] Update the **Surprise Me** description in Telegram so it accurately explains
  the stronger but controlled exploration now used by the backend.
- [x] Improve the deterministic profile summary so it adds insight beyond repeating
  the top three colours and style traits already displayed in `/profile`.
- [x] Refine `/check` evidence wording for more natural singular/plural grammar and
  less repetitive dimension phrases while preserving deterministic grounding.
- [x] Replace or clarify the vague semantic-only `/check` evidence sentence when
  structured visual evidence is limited.
- [x] Make generic retry errors more actionable and propagate an operational request
  reference from Telegram through backend logs and user-facing failure messages.
  Production monitoring still needs to ingest and search those logs.

Keep fixed templates for command guidance, progress, headers, confirmations,
safety disclaimers, destructive-action warnings, correction previews, and known
error mappings. Their consistency improves usability and should not be replaced
with free-form AI text.

## V2 Roadmap

### V2.1: Completed

- [x] Fashion Presentation Preference: AURA asks before the first suggestion and
  allows later changes through `/settings`. It is never inferred from names or
  images and does not affect profile construction or `/check` scoring.
- [x] Improved `/check` Explanations: version 5 explanations are item-specific,
  evidence-grounded, structured, and retain subjective language without changing
  the deterministic score.

The user manually tested the current V2.1 flows and accepted them as V2.1.

### V2.2: Completed

- [x] Wardrobe Browser: `/wardrobe` lists active owned items ten per page, opens
  the exact retained private image, and shows the effective analysis.
- [x] Guided Item Editing: **Edit Item Details** supports Item Name, Item Type,
  Colours, Patterns, Materials, Textures, Style Traits, Shape Traits, and
  Decorative Details. Description is intentionally not editable.
- [x] Editing UX: AURA shows the current value, examples, and a Current Value vs
  New Value preview. Users can return to editable fields, discard changes, or
  return to the item without losing navigation context.
- [x] Typed values: comma-separated input replaces the selected field. Common
  synonyms, free-text item types, and colour names are normalized. Unknown
  controlled values are rejected with close suggestions and nothing is saved.
- [x] Correction safety: original AI analysis stays immutable, corrections are
  versioned, canonical text and embeddings are regenerated, and the profile is
  rebuilt. A failed rebuild restores the previous active correction.
- [x] Vocabulary migration: feature and embedding schema revision 2 expands the
  correction vocabulary without automatically reanalyzing existing images or
  regenerating their embeddings.

Validation completed after V2.2 implementation:

- backend test suite: 85 passed;
- Telegram test suite: 39 passed;
- Supabase correction and vocabulary migrations applied remotely;
- existing records promoted to schema revision 2 through metadata migration.

Validation completed after the suggestion-diversity and command cleanup:

- backend test suite: 89 passed;
- Telegram test suite: 37 passed;
- suggestion-history migration applied and verified on linked Supabase.

Validation completed after the user-facing template improvement pass:

- backend test suite: 95 passed;
- Telegram test suite: 38 passed;
- request references verified across Telegram client errors and FastAPI responses.

### V2: Planned or Deferred

- [ ] Review and prioritize user-experience improvements from tester feedback.
  Current feedback confirms that the application works but can be easier and
  smoother to use; specific changes will be agreed before implementation.
- [x] Remove the standalone `/remove` command and keep item removal inside
  `/wardrobe` to avoid duplicate user flows.
- [ ] Consider an explicit user-triggered **Reanalyze Item** action for old
  uploads. Do not automatically reprocess existing items because results and
  provider costs could change without user intent.
- [ ] Build a consented evaluation dataset from corrections and feedback before
  attempting learned personalization or model training.
- [ ] Revisit learned personalization only after enough high-quality user data
  exists. The current expected test group of roughly three users is too small
  for meaningful retraining.
- [ ] Revisit body-type input only if AURA later supports fit-focused or outfit
  guidance. It does not currently improve the aesthetic-matching objective.

## Accepted Product Decisions

- AURA is an aesthetic matcher, not an objective fashion judge.
- Profiles remain multidimensional rather than assigning one rigid style label.
- Owned-item photos should contain one clear primary item; albums represent
  several different items rather than several views of one item.
- Image-derived item names are used when users do not provide captions.
- Generated suggestion images are references, not products or retailer claims.
  AURA does not persist them; they remain in Telegram under Telegram's retention.
- Fashion presentation is self-reported and applies only to suggestions.
- Body type is deferred because the current product does not provide fit advice.
- Candidate checks and feedback do not silently retrain or mutate the profile.
- Corrections affect the active profile while preserving original analysis and
  provenance for debugging, evaluation, and explainability.
- Unsupported correction values are not silently stored. AURA suggests nearby
  accepted terms so the user can revise the input.
- Description editing is not planned for guided corrections.
- Major AI, scoring, database, or deployment changes require an explicit design
  decision before implementation.

## Maintenance Rule

When work changes release scope, update this file and the summary in
`docs/PROJECT_CONTEXT.md`. Keep implementation details in `docs/AI_PIPELINE.md`
and `docs/DATABASE_SCHEMA.md`, and keep local operation instructions in
`README.md`.
