# AURA Delivery Roadmap and Session Handoff

This document is the durable handoff for product decisions, completed work, and
remaining tasks. Update it whenever a feature is accepted, deferred, or changed
so progress does not depend on chat history.

Last updated: 2026-10-18

## Release Status

### V1 and V2.3: Demonstration Release Online

Implemented and locally verified:

- `/add` for individual photos and Telegram albums, using one primary belonging
  per photo and processing up to ten photos in each Telegram media group;
- AI visual-feature extraction, canonical feature text, semantic embeddings,
  and deterministic profile aggregation after five usable owned items;
- `/profile` with the user's Telegram display name, collection progress, and
  formatted style-profile sections;
- `/check` with Classification, Matching Evidence, Contrasting Evidence, and
  Subjective Qualifier sections, persistent single-photo or album processing,
  and explicit `/done` exit behavior;
- two separately labeled feedback questions after `/check`: Fits my taste or Not
  my taste, followed by Bought it or Passed on it;
- `/suggestion` with intent and category selection, three initial generated
  references, an optional two more, controls below the images, setup cancellation,
  and Finish Suggestions;
- `/settings` for self-reported Menswear, Womenswear, Gender-neutral, or No
  preference presentation choices used only by suggestions;
- item removal through `/wardrobe`, with confirmation, cancellation, and pagination;
- `/resetprofile` with confirmation while retaining candidate checks and
  feedback history;
- private Supabase image storage, PostgreSQL/pgvector persistence, migrations,
  AI-provider adapters, and a combined local restart script.

The release works locally and as a Railway-hosted hackathon demonstration. It is
not yet production-ready for unrestricted public usage.

### V1: Completed Validation

- [x] Manually test the V2.2 `/wardrobe` and guided item-editing flows. Both are
  working as expected.
- [x] Collect initial feedback from test users. Users reported that AURA works,
  while identifying general user-experience improvements to address later.
- [x] Separate `/check` feedback into clearly labeled taste and purchase-decision
  questions while retaining the existing independent feedback categories.
- [x] Replace each answered feedback prompt and its buttons with a persistent
  confirmation that names the recorded taste or decision response.
- [x] Improve Telegram interaction continuity: keep `/check` active until `/done`,
  support candidate albums, show explicit `/add` and `/check` mode reminders,
  remove saved `/settings` controls, add `/suggestion` cancellation, and delete
  selected wardrobe-item messages when returning to the browser.

### Submission Demonstration

AURA will be submitted with a Railway-hosted backend and Telegram worker. The
local launcher remains available for development and recovery testing.

- [x] Authenticate every `/v1` Telegram-to-backend request with a shared bearer
  credential before trusting the asserted Telegram user identity. Keep `/health`
  public for hosting monitoring and return request-referenced authentication errors.
- [x] Create and verify a manual Supabase backup covering roles, schema, data,
  Storage metadata, and all private `item-images` objects with SHA-256 manifests.
  The current project exposes no Supabase-managed restore points and has PITR off.
- [x] Run one final local acceptance pass using `restart-aura.ps1`, covering
  `/add`, `/profile`, `/check`, feedback, `/suggestion`, `/wardrobe`, item editing,
  item reanalysis, removal cancellation, and `/resetprofile` cancellation. All
  flows passed on 18 October 2026. The editing pass also added and verified a
  missing **Back to Editable Fields** control on the correction preview.
- [x] Review final documentation for implemented behavior, local setup, release
  scope, test status, backup limitations, and deferred production work.
- [x] Manually smoke-test the latest interaction-continuity changes: persistent
  single-photo and album `/check`, `/done`, saved `/settings`, `/suggestion`
  cancellation, and **Back to Wardrobe** message cleanup. The user confirmed all
  flows work correctly after implementation.
- [x] Scan the exact staged submission files for known credential formats,
  embedded connection credentials, sensitive paths, and suspicious secret
  assignments. No exposed credentials were found.
- [x] Commit and push the tested application state.
- [x] Deploy `aura-backend` and `aura-telegram` as separate Railway services using
  repository Dockerfiles, private runtime variables, one Telegram replica, and a
  public backend healthcheck.
- [x] Verify hosted `/start`, `/profile`, and `/check` interactions and confirm the
  corresponding requests in Railway backend logs.
- [x] Document Railway deployment, verification, restart, rollback, and Supabase
  recovery boundaries in `docs/DEPLOYMENT.md`.
- [x] Add a responsive public landing page at the Railway backend root describing
  AURA's value, capabilities, architecture, and responsible-AI boundaries without
  exposing the private Telegram bot link. The optional demo destination is supplied
  through the backend-only `AURA_PUBLIC_TELEGRAM_URL` environment variable. Backend
  validation: 110 tests passed.
- [ ] At the end of submission preparation, add the deployed project and Telegram
  bot links only to Devpost and approved social materials. Do not expose the bot
  link in the GitHub README. Confirm the repository is public and test each
  submitted link while signed out.
- [ ] Capture demonstration screenshots and video, publish the required LinkedIn
  reflection, and complete the Devpost entry.

### Post-Submission Production Work

These tasks remain deferred because the Railway deployment is a limited public
demonstration rather than a production service:

- [ ] Add per-user and provider-aware rate limits plus cost controls for vision,
  embeddings, and image generation before allowing broader or public access.
- [ ] Configure production monitoring and actionable error reporting.
- [ ] Copy verified backups to an encrypted off-device location and complete one
  restore drill against a disposable Supabase project before relying on recovery.
- [x] Select demonstration hosting for the FastAPI service and Telegram worker,
  configure hosted secrets, and prepare deployment and recovery instructions.
- [x] Run the backend and Telegram worker as hosted services so normal operation
  does not depend on manually running `restart-aura.ps1`.
- [ ] Upgrade restart guarantees, alerting, and operational ownership before
  treating the hosted services as production-ready.

### V1: Remaining Quality Work

- [x] Add a short `/suggestion` disclaimer explaining that small or visually
  similar profiles may produce similar ideas, and that adding more varied owned
  items can broaden the profile evidence.
- [x] Improve suggestion diversity by remembering recent concepts, avoiding
  repetition across sessions, rotating secondary visual traits, varying catalog
  selection, and making **Surprise Me** more exploratory.
- [ ] Evaluate classifications and explanations on approximately 30-50
  representative owned and candidate images if the submission schedule permits.
- [x] Review collected user feedback and implement the agreed user-experience
  improvements, including persistent `/check` mode with albums, clearer mode
  reminders, cleaned settings and wardrobe messages, and suggestion cancellation.

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

Validation completed after separating the feedback questions and adding persistent
answer confirmations:

- Telegram test suite: 42 passed;
- backend feedback service and API tests: 7 passed;
- existing `TASTE` and `DECISION` persistence categories remain unchanged.

Validation completed after user-triggered item reanalysis:

- backend test suite: 101 passed;
- Telegram test suite: 44 passed;
- reanalysis migration `20261018020000` applied and verified on linked Supabase;
- preview, confirmation, discard, manual-correction replacement warning, profile
  rebuild, and rollback behavior covered by automated tests.

Validation completed after Telegram-to-backend authentication:

- backend test suite: 104 passed;
- Telegram test suite: 45 passed;
- missing and incorrect credentials return `401` before asserted Telegram identity
  is trusted, while the correctly authenticated client and public `/health` route
  are covered by automated tests;
- `restart-aura.ps1` fails clearly when the shared secret is missing or too short.

### V2.3: Completed

- [x] Present taste and purchase-decision feedback as separate questions and
  replace answered controls with clear recorded confirmations.
- [x] Add user-triggered **Reanalyze Item** with an AI-cost warning, current versus
  proposed preview, explicit save or discard, provenance, and profile rollback.
- [x] Keep `/check` active until `/done`, accept candidate albums, and display
  explicit mode reminders after individual and batch processing.
- [x] Improve Telegram cleanliness by removing saved `/settings` controls, adding
  `/suggestion` cancellation, and deleting selected item messages on return to
  `/wardrobe`.

Validation completed after the V2.3 interaction-continuity pass:

- backend test suite: 104 passed;
- Telegram test suite: 48 passed;
- the earlier primary-flow acceptance pass remains valid, and the latest
  interaction-continuity changes passed both automated coverage and the user's
  manual Telegram smoke test.

### V2: Planned or Deferred

- [x] Remove the standalone `/remove` command and keep item removal inside
  `/wardrobe` to avoid duplicate user flows.
- [ ] Build a consented evaluation dataset from corrections and feedback before
  attempting learned personalization or model training.
- [ ] Revisit learned personalization only after enough high-quality user data
  exists. The current expected test group of roughly three users is too small
  for meaningful retraining.
- [ ] Revisit body-type input only if AURA later supports fit-focused or outfit
  guidance. It does not currently improve the aesthetic-matching objective.

### V3: Product Suggestions for Later Evaluation

- [ ] **Preview on Me:** explore an optional virtual try-on visualization that
  places an AURA suggestion onto a user-provided photo. Treat the result as an
  artistic preview rather than a sizing or physical-fit prediction, require
  explicit consent, minimize retention of personal photos, and keep the feature
  separate from profile construction and `/check` scoring.
- [ ] **Real Product Discovery:** explore a separate `/shop` flow that finds real
  purchasable items through authorized retailer APIs or product feeds. Preserve
  `/suggestion` as non-commercial inspiration, avoid arbitrary web scraping,
  disclose retailer or affiliate relationships, and account for region, price,
  availability, image-use rights, rate limits, and stale product data.

Both ideas can support AURA's broader aesthetic-matching vision, but they remain
outside the current MVP and V2 scope. Either feature requires an explicit product,
privacy, provider, cost, and architecture decision before implementation.

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
and `docs/DATABASE_SCHEMA.md`, local operation instructions in `README.md`, and
hosted operating procedures in `docs/DEPLOYMENT.md`.
