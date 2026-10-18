# AURA

AURA is an AI-powered aesthetic matcher that learns from belongings a user likes
and explains how a candidate item may fit or contrast with that profile.

## Local Setup

1. Copy `.env.example` to `.env` and fill in the Supabase, AI provider, and
   Telegram settings. `SUPABASE_DB_PASSWORD` and `SUPABASE_ACCESS_TOKEN` are
   needed by the backup script rather than normal application startup. OpenAI
   image settings are optional unless `/suggestion` will be demonstrated.
   Generate one random value of at least 32 characters for
   `AURA_INTERNAL_API_KEY`; the shared repository `.env` supplies the same value
   to both the backend and Telegram worker. For example:

   ```powershell
   $bytes = New-Object byte[] 32
   [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
   [Convert]::ToBase64String($bytes)
   ```
2. Install and run the backend:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   .\.venv\Scripts\python.exe -m uvicorn aura_backend.main:app --reload
   ```

3. In another terminal, install and run the Telegram adapter:

   ```powershell
   cd telegram-bot
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   .\.venv\Scripts\python.exe -m aura_telegram
   ```

Create `TELEGRAM_BOT_TOKEN` through Telegram's BotFather. Keep both processes
running during local development.

After completing the setup once, start or restart both services in one terminal:

```powershell
.\restart-aura.ps1
```

If Windows execution policy blocks the script, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\restart-aura.ps1
```

The script stops existing AURA processes started from these virtual environments,
starts the backend and Telegram bot together, and stops both when you press
`Ctrl+C`.

Create a verified manual backup of the linked Supabase database and private image
bucket with:

```powershell
.\backup-supabase.ps1
```

Docker Desktop must be running. Backups contain private user data, are excluded
from Git, and should be copied to encrypted off-device storage. See
`docs/BACKUP_AND_RECOVERY.md` for verification and recovery instructions.

## Local Verification

Run the automated suites from the repository root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\telegram-bot
.\.venv\Scripts\python.exe -m pytest -q
cd ..
```

With AURA running, verify the public backend health endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Telegram Flow

- `/start` displays the available actions.
- `/add` accepts one photo or an album of up to ten different belongings and builds
  the profile after at least five usable items. Every photo must show one clear
  primary item. Captions are optional because AURA can use the vision-inferred name.
- `/check` remains active until `/done` and accepts either one candidate photo or
  an album of up to ten different candidates. Every photo receives its own
  explainable match result and feedback controls.
- Inline buttons capture taste and purchase-decision feedback.
- `/profile` shows the current style profile or progress toward the five-item minimum.
- `/settings` stores an optional Menswear, Womenswear, Gender-neutral, or No
  preference choice for generated clothing ideas. It does not change the style
  profile or `/check` scoring.
- `/suggestion` lets the user choose an aesthetic direction and an optional
  category: Tops, Outerwear, Pants, Accessories, Footwear, or Any Category. It
  generates three profile-guided wardrobe reference images and can generate two
  more, up to five per interaction. Controls appear below each generated batch,
  and the user can cancel setup or finish after the first three. AURA avoids recently generated
  concepts and varies secondary profile traits across sessions. Images are
  inspiration only and are not shopping recommendations or profile inputs.
- `/wardrobe` browses uploaded belongings ten per page. Selecting an item shows
  its stored private image and current analysis, with actions to correct, reanalyze,
  or remove it.
- **Edit Item Details** shows the selected field's current value, accepts natural
  typed corrections with comma-separated values, normalizes common synonyms and
  colour names, then shows a before-and-after preview. Saving preserves the
  original AI analysis, creates a versioned correction, and rebuilds the profile.
- **Reanalyze Item** reruns the current AI pipeline only after an AI-cost warning,
  shows the current and proposed analyses, and changes the profile only after the
  user confirms. Discarding keeps the current item and profile unchanged.
- `/resetprofile` clears all owned items from the active profile after confirmation.
- `/help` displays the command guide and photo tips.
- `/done` exits the current `/add` or `/check` photo mode.

Telegram albums can contain at most ten photos per media group. If a user selects
more than ten, Telegram sends multiple groups and AURA processes each group as a
separate batch. Use one clear primary belonging per photo for the most reliable
analysis.

## Current Status

The local MVP is implemented and manually verified across `/add`, `/profile`,
`/check`, feedback buttons, `/suggestion`, `/wardrobe`, and `/resetprofile`.
V2.1 adds fashion-presentation settings for suggestions and clearer,
item-specific version 5 `/check` explanations. V2.2 adds a private wardrobe
browser and confirmed, guided corrections to owned-item analysis. V2.3 adds
separate feedback signals, user-triggered item reanalysis, persistent candidate
checking with album support, and cleaner Telegram interaction controls.
The latest automated results are 104 backend tests and 48 Telegram tests passing.
Telegram-to-backend requests are authenticated with a shared bearer
credential; `/health` remains public for service monitoring. Production deployment
remains future work; see `docs/PROJECT_CONTEXT.md` for the architecture and
`docs/ROADMAP.md` for completed work and remaining tasks.

The bot refreshes its Telegram command menu automatically when it starts.

The Telegram package is only a frontend adapter. It authenticates to FastAPI,
sends images and asserted Telegram identity headers, and contains no prompts,
scoring, profile, or persistence logic. Never expose `AURA_INTERNAL_API_KEY` in
Telegram messages, client logs, or a public frontend.
