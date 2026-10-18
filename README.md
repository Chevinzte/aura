# AURA

AURA is an AI-powered aesthetic matcher that learns from belongings a user likes,
builds a multidimensional style profile, and explains how another item may fit or
intentionally contrast with that profile.

## Problem Statement

People often know whether they like individual belongings but struggle to describe
the visual patterns connecting them. Generic fashion labels and recommendation
feeds can flatten personal taste into one trend, while purchase decisions still
leave the user asking: **Does this item fit my aesthetic?**

AURA is designed for people who want understandable, personalized guidance based
on their own belongings rather than an objective fashion verdict.

## Solution Overview

Users interact with AURA through Telegram. They upload belongings they genuinely
like, and AURA extracts observable visual features such as colours, materials,
patterns, shapes, details, and style traits. After five usable items, AURA builds
a profile and can:

- explain whether a candidate is a strong fit, moderate fit, intentional contrast,
  weak fit, or uncertain;
- show the evidence behind that assessment;
- generate non-commercial wardrobe inspiration;
- let users inspect, correct, reanalyze, or remove profile items;
- retain versioned evidence for explainability without silently retraining from
  every interaction.

The Telegram client is only an interface adapter. Profile construction, matching,
AI orchestration, persistence, and safety rules remain in the FastAPI backend.

## Key Features

- **Profile building:** `/add` accepts individual photos or albums of different
  belongings, with one clear primary item per photo.
- **Explainable matching:** `/check` stays active until `/done`, supports albums,
  and returns Classification, Matching Evidence, Contrasting Evidence, and a
  Subjective Qualifier for every item.
- **Style profile:** `/profile` presents leading colours, style traits, patterns,
  materials, shapes, details, influences, and an evidence-based summary.
- **Wardrobe inspiration:** `/suggestion` creates three AI-generated single-item
  references, with an optional two more, across selectable wardrobe categories.
- **Presentation preference:** `/settings` applies an optional Menswear,
  Womenswear, Gender-neutral, or No preference constraint to suggestions only.
- **Private wardrobe browser:** `/wardrobe` displays retained uploads and supports
  guided item correction, confirmed reanalysis, and removal.
- **Feedback capture:** AURA separately records whether an item suits the user's
  taste and whether they bought or passed on it.
- **Profile controls:** `/resetprofile` removes active owned-item inputs after
  explicit confirmation while preserving candidate and feedback history.

Telegram media groups contain at most ten photos. If a user chooses more than ten,
Telegram sends multiple groups and AURA processes each group independently.

## AI Integration

AURA uses AI for bounded perception and generation rather than delegating the
entire product decision to a language model:

```text
Uploaded image
  -> image validation
  -> structured visual-feature extraction
  -> canonical feature text
  -> semantic text embedding
  -> deterministic profile aggregation
  -> deterministic candidate/profile comparison
  -> evidence-grounded explanation
  -> optional feedback capture
```

- `gemini-3.5-flash-lite`, accessed through the AI Lodge OpenAI-compatible API,
  extracts schema-validated observable visual features.
- `text-embedding-3-small` embeds canonical feature text into 1,536 dimensions as
  a secondary semantic signal.
- Deterministic application logic builds profiles, combines matching dimensions,
  assigns classifications, and selects grounded evidence. The vision model does
  not decide the final match.
- The OpenAI Images API optionally generates isolated, product-style reference
  images for `/suggestion`. These images never become profile evidence.
- Provider model identifiers remain environment configuration behind
  provider-neutral adapters.

See `docs/AI_PIPELINE.md` for prompts, schemas, scoring, explanation rules, and
failure handling.

## External Tools & Datasets

- **Telegram Bot API:** conversational user interface and photo delivery.
- **FastAPI and Uvicorn:** backend API and application server.
- **Supabase PostgreSQL and pgvector:** application records, vector storage, and
  profile provenance.
- **Supabase Storage:** private retention of uploaded item images.
- **AI Lodge API:** OpenAI-compatible access to the configured vision and embedding
  models.
- **OpenAI Images API:** optional generated reference images for `/suggestion`.
- **Railway:** always-on demonstration hosting for the backend and Telegram worker.

AURA uses no public training dataset. Its active profile is calculated only from
the current user's successfully analyzed owned items. Corrections and feedback
are stored for provenance and future consented evaluation; they do not currently
train a model or automatically alter matching rules.

## Architecture

```text
Telegram user
     |
     v
Telegram Bot API
     |
     v
Railway: aura-telegram
     |
     | authenticated HTTPS
     v
Railway: aura-backend ----> Supabase PostgreSQL + Storage
     |
     +----> AI Lodge API
     |
     `----> OpenAI Images API
```

Every `/v1` request from the Telegram worker carries a shared bearer credential.
Only `/health` is public and unauthenticated. Supabase and AI-provider credentials
exist only in the backend environment.

## Installation & Setup

### Prerequisites

- Python 3.12 or newer;
- a Telegram bot token from BotFather;
- a Supabase project with the repository migrations applied;
- an AI Lodge-compatible API key;
- an OpenAI Platform API key only when `/suggestion` image generation is enabled.

### Environment

Copy `.env.example` to `.env` and replace every required placeholder. Generate one
random value of at least 32 characters for `AURA_INTERNAL_API_KEY`; the backend and
Telegram worker must use the same value.

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

`SUPABASE_DB_PASSWORD` and `SUPABASE_ACCESS_TOKEN` are used by the backup workflow,
not normal application startup. Never commit `.env`.

Set `AURA_PUBLIC_TELEGRAM_URL` only in the deployed backend environment when the
landing-page **Try AURA on Telegram** button should be active. This keeps the real
bot address out of the public repository.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn aura_backend.main:app --reload
```

### Telegram Worker

In another terminal:

```powershell
cd telegram-bot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m aura_telegram
```

After initial setup, both local processes can be managed together from the
repository root:

```powershell
.\restart-aura.ps1
```

If PowerShell blocks the script:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\restart-aura.ps1
```

Do not run the local Telegram worker while the Railway worker is active. Telegram
long polling should have one active worker for this bot token.

## Testing

Run both automated suites from the repository root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\telegram-bot
.\.venv\Scripts\python.exe -m pytest -q
cd ..
```

The latest verified result is `110` backend tests and `48` Telegram tests passing.
The complete Telegram flow has also been manually accepted with individual photos,
albums, profile construction, matching, feedback, suggestions, wardrobe browsing,
corrections, reanalysis, removal, and profile reset.

## Deployment

AURA's hackathon demonstration deployment runs as two Railway services built from
the repository Dockerfiles:

- `aura-backend`, rooted at `/backend`, with public `/health` monitoring;
- `aura-telegram`, rooted at `/telegram-bot`, with no public domain and one polling
  replica.

The backend root serves a responsive public product overview without exposing the
private Telegram bot link, user records, or service credentials.

The hosted `/start`, `/profile`, and `/check` flows have been manually verified,
including requests appearing in the deployed backend logs. Detailed deployment,
verification, restart, rollback, and recovery instructions are in
`docs/DEPLOYMENT.md`.

## AI Safety & Limitations

- **Subjective output:** AURA presents guidance, not an objective statement of
  taste, attractiveness, suitability, value, or identity.
- **Grounded explanations:** User-facing evidence is selected from validated item
  and profile features. Unsupported free-form model recommendations are excluded.
- **Deterministic boundary:** Models perceive visual features and generate optional
  references; deterministic code owns profile aggregation and match classification.
- **Candidate isolation:** Checking an item never silently adds it to the user's
  owned profile.
- **Explicit control:** Destructive actions, item corrections, and AI reanalysis
  require confirmation. Original analyses and accepted revisions remain available
  for provenance.
- **Privacy boundary:** Images are stored in a private bucket. Permanent public
  image URLs and server credentials are not sent to Telegram.
- **Preference safety:** Fashion presentation is self-reported and never inferred
  from a name, body, or photograph. It affects suggestions only.
- **No automatic learning:** Feedback and corrections do not retrain a model or
  personalize scoring automatically. The current test population is too small for
  responsible learned personalization.
- **Visual uncertainty:** Occlusion, poor lighting, multiple primary items, unusual
  garments, or provider failures can produce incomplete or incorrect features.
- **Scope limitation:** AURA does not provide sizing, body-fit, authenticity,
  shopping, pricing, medical, or financial advice. Generated images are inspiration,
  not purchasable products.
- **Profile limitations:** A five-item minimum provides only an initial signal.
  Small or visually similar collections may lead to repetitive suggestions.
- **Operational dependency:** Availability depends on Railway, Supabase, Telegram,
  AI Lodge, and OpenAI quotas and service health. The demonstration deployment has
  limited monitoring, rate controls, and recovery guarantees.

See `docs/PROJECT_CONTEXT.md` for accepted product boundaries,
`docs/BACKUP_AND_RECOVERY.md` for data recovery, and `docs/ROADMAP.md` for completed
scope and deferred work.
