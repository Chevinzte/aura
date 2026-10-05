# AURA Database and Storage Schema

## Status

Accepted design target for the PostgreSQL and Supabase MVP.

This document defines the persistence contract supporting the AI pipeline in
`AI_PIPELINE.md`. The first SQL migration should implement this design without
adding Supabase Auth or exposing Supabase directly to Telegram.

## Goals

The persistence layer must:

- keep users and their belongings isolated;
- preserve the exact AI and profile versions used for each match;
- support deterministic retries and profile rebuilding;
- store explainable evidence alongside internal scores;
- keep user images private;
- allow future model migrations without overwriting incompatible results;
- remain usable by frontends other than Telegram.

## Technology Decisions

- Database: Supabase PostgreSQL
- Structured AI data: PostgreSQL `JSONB`
- Embeddings: pgvector `vector(1536)`
- Images: private Supabase Storage bucket
- MVP identity: Telegram user ID
- Database access: FastAPI backend using server-side credentials
- Supabase Auth: not used for the MVP
- Primary keys: application-generated UUIDs
- Timestamps: timezone-aware PostgreSQL timestamps stored in UTC

Approximate vector search is not required for the MVP. AURA compares a candidate
with one user's active profile, so exact cosine comparison in application code is
sufficient. A vector index should be added only when a measured query pattern
requires cross-record similarity search at scale.

## Extensions

The initial migration enables:

```sql
create extension if not exists vector;
create extension if not exists pgcrypto;
```

`pgcrypto` provides `gen_random_uuid()` if IDs are generated in PostgreSQL. The
application may generate UUIDs instead, but one strategy should be used
consistently.

## Enum Types

The MVP uses PostgreSQL enums for stable lifecycle and domain values:

```text
item_source:
  OWNED
  CANDIDATE

item_status:
  UPLOADED
  ANALYZING
  READY
  FAILED

analysis_status:
  PENDING
  PROCESSING
  COMPLETED
  FAILED

match_classification:
  STRONG_FIT
  MODERATE_FIT
  INTENTIONAL_CONTRAST
  WEAK_FIT
  UNCERTAIN

feedback_category:
  TASTE
  DECISION

feedback_type:
  LIKE
  DISLIKE
  BOUGHT
  NOT_BOUGHT
```

Enums are appropriate for these values because changes represent explicit
domain migrations. Flexible AI-generated traits belong in versioned JSONB, not
database enums.

## Tables

### `users`

Represents an AURA user independently of any frontend authentication system.

| Column | Type | Rules |
| --- | --- | --- |
| `id` | `uuid` | Primary key |
| `telegram_user_id` | `bigint` | Required, unique |
| `display_name` | `text` | Nullable |
| `onboarding_complete` | `boolean` | Required, default `false` |
| `created_at` | `timestamptz` | Required, default `now()` |
| `updated_at` | `timestamptz` | Required, default `now()` |

The Telegram identifier is an external identifier, not the domain primary key.
Future authentication methods can map to the same UUID without changing item,
profile, or match relationships.

### `items`

Represents one uploaded object. An item owns its image-storage reference but not
its AI results.

| Column | Type | Rules |
| --- | --- | --- |
| `id` | `uuid` | Primary key |
| `user_id` | `uuid` | Required, references `users(id)` |
| `source` | `item_source` | Required |
| `status` | `item_status` | Required, default `UPLOADED` |
| `storage_bucket` | `text` | Required |
| `storage_path` | `text` | Required, unique |
| `original_filename` | `text` | Nullable, display/diagnostic use only |
| `mime_type` | `text` | Required |
| `size_bytes` | `bigint` | Required, greater than zero |
| `width_px` | `integer` | Nullable until decoded, greater than zero |
| `height_px` | `integer` | Nullable until decoded, greater than zero |
| `content_sha256` | `text` | Required, lowercase hexadecimal SHA-256 |
| `item_name` | `text` | Nullable user-facing name |
| `deleted_at` | `timestamptz` | Nullable soft-deletion marker |
| `created_at` | `timestamptz` | Required, default `now()` |
| `updated_at` | `timestamptz` | Required, default `now()` |

`content_sha256` supports duplicate detection and idempotency. Duplicate images
are permitted, but profile aggregation reduces their influence. A unique
constraint on `(user_id, content_sha256)` is intentionally not used because a
user may upload the same image in different workflows.

Soft-deleted items do not contribute to new profiles or matches. Historical
analyses may continue referencing them until user deletion.

### `item_visual_features`

Represents one versioned feature-extraction and embedding run for an item.
Failed attempts are retained for operational diagnosis without containing raw
provider reasoning.

| Column | Type | Rules |
| --- | --- | --- |
| `id` | `uuid` | Primary key |
| `item_id` | `uuid` | Required, references `items(id)` |
| `status` | `analysis_status` | Required, default `PENDING` |
| `features` | `jsonb` | Nullable until completed |
| `canonical_embedding_text` | `text` | Nullable until features validate |
| `embedding` | `vector(1536)` | Nullable until embedding succeeds |
| `vision_provider` | `text` | Required |
| `vision_model` | `text` | Required |
| `vision_prompt_version` | `integer` | Required, greater than zero |
| `feature_schema_version` | `integer` | Required, greater than zero |
| `embedding_provider` | `text` | Required |
| `embedding_model` | `text` | Required |
| `embedding_dimensions` | `integer` | Required, equals 1536 for version 1 |
| `embedding_schema_version` | `integer` | Required, greater than zero |
| `attempt_count` | `smallint` | Required, default zero, non-negative |
| `error_code` | `text` | Nullable stable application error code |
| `error_detail` | `text` | Nullable sanitized operational detail |
| `started_at` | `timestamptz` | Nullable |
| `completed_at` | `timestamptz` | Nullable |
| `created_at` | `timestamptz` | Required, default `now()` |
| `updated_at` | `timestamptz` | Required, default `now()` |

Required constraints:

- `COMPLETED` records have non-null features, canonical text, embedding, and
  completion timestamp.
- `FAILED` records have a non-null stable error code and completion timestamp.
- Only one run exists for an item and a complete pipeline-version tuple.
- `embedding_dimensions` must match the vector column contract.
- Application validation remains authoritative for the internal JSON schema;
  the database checks that `features` is a JSON object when present.

Pipeline-version uniqueness uses:

```text
(item_id,
 vision_provider,
 vision_model,
 vision_prompt_version,
 feature_schema_version,
 embedding_provider,
 embedding_model,
 embedding_dimensions,
 embedding_schema_version)
```

Retries update the same run's status and attempt count. A materially different
pipeline creates a new record rather than overwriting the old result.

### `aesthetic_profiles`

Represents an immutable, versioned profile snapshot. Rebuilding a profile
creates a new row and marks the previous row inactive.

| Column | Type | Rules |
| --- | --- | --- |
| `id` | `uuid` | Primary key |
| `user_id` | `uuid` | Required, references `users(id)` |
| `is_active` | `boolean` | Required, default `false` |
| `profile_data` | `jsonb` | Required object |
| `embedding_centroid` | `vector(1536)` | Required |
| `colour_diversity` | `double precision` | Required, from 0.0 to 1.0 |
| `style_diversity` | `double precision` | Required, from 0.0 to 1.0 |
| `generated_summary` | `text` | Required, evidence-derived |
| `contributing_item_count` | `integer` | Required, at least five |
| `profile_algorithm_version` | `integer` | Required, greater than zero |
| `feature_schema_version` | `integer` | Required, greater than zero |
| `embedding_model` | `text` | Required |
| `embedding_dimensions` | `integer` | Required, equals 1536 for version 1 |
| `embedding_schema_version` | `integer` | Required, greater than zero |
| `created_at` | `timestamptz` | Required, default `now()` |

Only one active profile is allowed per user through a partial unique index. A
profile is immutable after creation except for activation state. Activation of a
new snapshot and deactivation of the prior snapshot occur in one transaction.

### `aesthetic_profile_items`

Records the exact feature-analysis rows contributing to a profile. This avoids
placing relational identifiers only inside JSONB and makes profile provenance
queryable.

| Column | Type | Rules |
| --- | --- | --- |
| `profile_id` | `uuid` | References `aesthetic_profiles(id)` |
| `item_visual_features_id` | `uuid` | References `item_visual_features(id)` |
| `effective_weight` | `double precision` | Required, greater than zero |
| `created_at` | `timestamptz` | Required, default `now()` |

The composite primary key is `(profile_id, item_visual_features_id)`. The
application ensures each contributing feature record belongs to an `OWNED`,
non-deleted item owned by the same user as the profile.

### `match_analyses`

Represents an immutable comparison between one candidate analysis and one exact
profile snapshot.

| Column | Type | Rules |
| --- | --- | --- |
| `id` | `uuid` | Primary key |
| `user_id` | `uuid` | Required, references `users(id)` |
| `candidate_item_id` | `uuid` | Required, references `items(id)` |
| `candidate_features_id` | `uuid` | Required, references `item_visual_features(id)` |
| `profile_id` | `uuid` | Required, references `aesthetic_profiles(id)` |
| `status` | `analysis_status` | Required, default `PENDING` |
| `overall_score` | `double precision` | Nullable, from 0.0 to 1.0 |
| `classification` | `match_classification` | Nullable until completed |
| `component_scores` | `jsonb` | Nullable object until completed |
| `matching_evidence` | `jsonb` | Nullable array until completed |
| `contrasting_evidence` | `jsonb` | Nullable array until completed |
| `explanation` | `text` | Nullable until completed |
| `scoring_version` | `integer` | Required, greater than zero |
| `explanation_version` | `integer` | Required, greater than zero |
| `error_code` | `text` | Nullable stable application error code |
| `error_detail` | `text` | Nullable sanitized operational detail |
| `started_at` | `timestamptz` | Nullable |
| `completed_at` | `timestamptz` | Nullable |
| `created_at` | `timestamptz` | Required, default `now()` |

Required constraints:

- The candidate item has source `CANDIDATE` and belongs to `user_id`.
- The candidate feature record belongs to the candidate item.
- The profile belongs to `user_id`.
- `COMPLETED` records have scores, classification, evidence, explanation, and a
  completion timestamp.
- `FAILED` records have an error code and completion timestamp.
- Completed results are immutable.

Cross-table ownership and source constraints are enforced in the application
service transaction because PostgreSQL check constraints cannot reference other
rows. Database foreign keys still prevent orphaned references.

Idempotent matching uses a unique constraint on:

```text
(candidate_features_id, profile_id, scoring_version, explanation_version)
```

Running the same match request returns the existing result. A new profile or
scoring version creates a new analysis.

### `feedback`

Stores explicit user feedback without changing the profile automatically.

| Column | Type | Rules |
| --- | --- | --- |
| `id` | `uuid` | Primary key |
| `user_id` | `uuid` | Required, references `users(id)` |
| `match_analysis_id` | `uuid` | Required, references `match_analyses(id)` |
| `category` | `feedback_category` | Required |
| `feedback_type` | `feedback_type` | Required |
| `note` | `text` | Nullable, length-limited by application |
| `created_at` | `timestamptz` | Required, default `now()` |
| `updated_at` | `timestamptz` | Required, default `now()` |

Each match has at most one feedback row per category through a unique constraint
on `(match_analysis_id, category)`. Submitting new feedback for that category
updates the existing row.

Category and type consistency is enforced:

- `TASTE` accepts `LIKE` or `DISLIKE`;
- `DECISION` accepts `BOUGHT` or `NOT_BOUGHT`.

The application verifies that the match belongs to the user. Feedback remains
evaluation data in MVP version 1 and does not trigger profile rebuilding.

## Relationships

```text
users
  1 -> many items
  1 -> many aesthetic_profiles
  1 -> many match_analyses

items
  1 -> many item_visual_features

aesthetic_profiles
  many <-> many item_visual_features through aesthetic_profile_items

match_analyses
  many -> 1 candidate item
  many -> 1 candidate feature analysis
  many -> 1 profile snapshot
  1 -> zero, one, or two feedback rows by category
```

## Indexes

The initial migration creates:

- unique B-tree index on `users(telegram_user_id)`;
- B-tree index on `items(user_id, created_at desc)` where `deleted_at is null`;
- B-tree index on `items(user_id, source, status)` where `deleted_at is null`;
- B-tree index on `items(user_id, content_sha256)`;
- B-tree index on `item_visual_features(item_id, created_at desc)`;
- B-tree index on `item_visual_features(status, created_at)` for retry workers;
- partial unique index on `aesthetic_profiles(user_id)` where `is_active`;
- B-tree index on `aesthetic_profiles(user_id, created_at desc)`;
- B-tree index on `aesthetic_profile_items(item_visual_features_id)`;
- B-tree index on `match_analyses(user_id, created_at desc)`;
- B-tree index on `match_analyses(candidate_item_id, created_at desc)`;
- B-tree index on `match_analyses(status, created_at)` for retry workers;
- B-tree index on `feedback(user_id, created_at desc)`.

No vector index is created initially. If later evaluation demonstrates a need,
the index type and operator class must match the chosen distance measure and
pgvector version.

## Timestamp Management

Tables with `updated_at` use one shared database trigger function to set it to
`now()` on update. Immutable completed records should be protected by application
rules and, where practical, database triggers that reject changes to result data
after completion.

## Supabase Storage

### Bucket

- Bucket name: `item-images`
- Visibility: private
- Accepted content: configured supported image MIME types only
- Uploads: performed by FastAPI, not Telegram directly

### Object Paths

Object paths use opaque identifiers rather than Telegram IDs or filenames:

```text
users/{user_uuid}/items/{item_uuid}/original.{extension}
```

The extension is derived from the validated MIME type. User-supplied filenames
must not determine the storage path.

### Access

- The backend stores only the bucket and object path.
- Signed URLs are generated only when a client or provider needs temporary
  access.
- Signed URLs use the shortest practical expiry and are never persisted.
- The service-role key stays in the FastAPI runtime and is never sent to a
  frontend.
- Logs must not contain signed URLs, image bytes, or service credentials.

For AI providers that accept image bytes, the backend should download the object
server-side and send bytes rather than create a public URL.

## Row Level Security

Enable Row Level Security on all application tables. The MVP exposes no direct
database access to Telegram or other clients, so no `anon` or `authenticated`
policies are required initially. The backend uses a protected server-side role
and enforces ownership in application services.

RLS is defense in depth, not a substitute for ownership checks. Every backend
operation receiving a user-scoped identifier must verify that the referenced
record belongs to the authenticated AURA user.

If direct Supabase client access is introduced later, it requires a separate
authentication and RLS design. Supabase Auth must not be introduced implicitly.

## Transactions and Concurrency

Use transactions for:

- creating an item and its initial analysis record;
- claiming an analysis for processing;
- completing or failing an analysis;
- creating and activating a new profile snapshot;
- creating or returning an idempotent match analysis;
- upserting feedback by category.

Profile rebuilding must serialize activation per user. The implementation may
use a row lock on the user or current active profile so concurrent owned-item
analyses cannot create two active profiles.

Workers claim pending records using a conditional update or row locking with
`skip locked`. API retries must not duplicate provider calls when another worker
already owns an active processing lease.

## Retention and Deletion

MVP defaults are:

- Retain original images while the user account exists.
- Retain historical feature analyses, profiles, matches, and feedback to preserve
  explainability and support evaluation.
- Do not retain raw provider responses or hidden reasoning in production.
- Soft-delete individual items first so historical references remain valid.
- Exclude soft-deleted items from all new profiles and analyses.

Deleting a user is an explicit backend workflow:

1. prevent new work for the user;
2. enumerate and delete the user's private storage objects;
3. hard-delete the user row;
4. allow foreign-key cascades to remove all dependent database records;
5. record only non-identifying operational confirmation.

Storage deletion occurs before database deletion because PostgreSQL foreign-key
cascades cannot delete Supabase Storage objects. The workflow must be retryable
when storage deletion partially fails.

## Foreign-Key Deletion Rules

- User-owned domain data uses `ON DELETE CASCADE` from `users`.
- Feature analyses use `ON DELETE CASCADE` from `items` only during final hard
  deletion.
- Profile contribution rows cascade from their profile and feature analysis.
- Match analyses cascade during user deletion but should otherwise be protected
  from accidental deletion through backend authorization.
- Feedback cascades from its match analysis.

The application normally soft-deletes items. Hard deletion is reserved for full
user deletion or an explicit administrative privacy workflow.

## Sensitive Data and Logging

Treat images, generated descriptions, feature data, and feedback as user data.

Production logs may include:

- internal UUIDs;
- pipeline versions;
- provider model identifiers;
- durations and token or request counts;
- stable error codes.

Production logs must not include:

- Telegram display names or raw Telegram identifiers unless operationally
  necessary and explicitly protected;
- image bytes or signed URLs;
- raw AI prompts containing user data;
- raw provider responses;
- embeddings;
- service-role keys or provider credentials.

## Migration Rules

- SQL migrations are append-only after being applied to a shared environment.
- Schema changes are introduced through new migrations, never by editing
  previously applied migrations.
- AI JSON structures are versioned by the application schema fields documented
  in `AI_PIPELINE.md`.
- Changing vector dimensions requires a new column or table migration; existing
  vectors must not be coerced into a new model space.
- New model or pipeline versions create new analysis rows.
- New profile algorithms create new snapshots.
- New scoring versions create new match analyses when recomputation is needed.

## Initial Implementation Sequence

1. Enable `vector` and `pgcrypto`.
2. Create enums and timestamp trigger function.
3. Create `users` and `items`.
4. Create `item_visual_features`.
5. Create `aesthetic_profiles` and `aesthetic_profile_items`.
6. Create `match_analyses` and `feedback`.
7. Add constraints and indexes.
8. Enable RLS without public client policies.
9. Create the private `item-images` bucket and storage restrictions.
10. Verify cascade, idempotency, active-profile, and feedback constraints with
    migration-level tests.

## Deferred Decisions

The following are intentionally deferred until usage or compliance requirements
justify them:

- approximate vector indexes;
- direct frontend access to Supabase;
- Supabase Auth;
- automatic archival schedules;
- per-user encryption keys;
- regional data-residency controls beyond the selected Supabase project region;
- automated learning from feedback;
- native image-embedding storage and weighting.
