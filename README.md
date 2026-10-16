# AURA

AURA is an AI-powered aesthetic matcher that learns from belongings a user likes
and explains how a candidate item may fit or contrast with that profile.

## Local Setup

1. Copy `.env.example` to `.env` and fill in the Supabase, AI provider, and
   Telegram settings.
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

The script stops existing AURA processes started from these virtual environments,
starts the backend and Telegram bot together, and stops both when you press
`Ctrl+C`.

## Telegram Flow

- `/start` displays the available actions.
- `/add` accepts a sequence of belongings the user likes and builds the profile
  after at least five usable items, with progress shown after each upload.
- `/check` accepts one candidate item and returns an explainable match result.
- Inline buttons capture taste and purchase-decision feedback.
- `/profile` shows the current style profile or progress toward the five-item minimum.
- `/remove` lists recent owned items and removes one after confirmation.
- `/resetprofile` clears all owned items from the active profile after confirmation.
- `/help` displays the command guide and photo tips.
- `/done` exits the current upload mode.

The bot refreshes its Telegram command menu automatically when it starts.

The Telegram package is only a frontend adapter. It sends images and identity
headers to FastAPI and contains no prompts, scoring, profile, or persistence
logic.
