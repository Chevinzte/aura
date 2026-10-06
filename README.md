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

## Telegram Flow

- `/start` displays the available actions.
- `/add` accepts a sequence of belongings the user likes and builds the profile
  after at least five usable items.
- `/check` accepts one candidate item and returns an explainable match result.
- Inline buttons capture taste and purchase-decision feedback.
- `/done` exits the current upload mode.

The Telegram package is only a frontend adapter. It sends images and identity
headers to FastAPI and contains no prompts, scoring, profile, or persistence
logic.
