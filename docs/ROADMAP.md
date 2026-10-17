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
- `/remove` with confirmation, cancellation, and pagination;
- `/resetprofile` with confirmation while retaining candidate checks and
  feedback history;
- private Supabase image storage, PostgreSQL/pgvector persistence, migrations,
  AI-provider adapters, and a combined local restart script.

V1 is working as a local MVP. It is not yet production-ready.

### V1: Remaining Production and Submission Work

- [ ] Authenticate Telegram-to-backend requests before exposing the backend.
- [ ] Select hosting for the FastAPI service and Telegram worker.
- [ ] Configure production secrets and environment separation.
- [ ] Add production monitoring and actionable error reporting.
- [ ] Add per-user and provider-aware rate limits.
- [ ] Configure and verify database and storage backups.
- [ ] Add cost controls for vision, embeddings, and image generation.
- [ ] Evaluate classifications and explanations on approximately 30-50
  representative owned and candidate images.
- [ ] Complete short onboarding and usability tests with real users.
- [ ] Prepare a deployment and recovery runbook for the final submission.

## V2 Roadmap

### V2.1: Completed

- [x] Fashion Presentation Preference: AURA asks before the first suggestion and
  allows later changes through `/settings`. It is never inferred from names or
  images and does not affect profile construction or `/check` scoring.
- [x] Improved `/check` Explanations: version 4 explanations are item-specific,
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

### V2: Planned or Deferred

- [ ] Decide whether `/remove` remains a permanent shortcut or is eventually
  removed from the command menu in favor of removal inside `/wardrobe`.
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
