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
- `/add` accepts one photo or an album of up to ten different belongings and builds
  the profile after at least five usable items. Every photo must show one clear
  primary item. Captions are optional because AURA can use the vision-inferred name.
- `/check` accepts one candidate item and returns an explainable match result.
- Inline buttons capture taste and purchase-decision feedback.
- `/profile` shows the current style profile or progress toward the five-item minimum.
- `/settings` stores an optional Menswear, Womenswear, Gender-neutral, or No
  preference choice for generated clothing ideas. It does not change the style
  profile or `/check` scoring.
- `/suggestion` lets the user choose an aesthetic direction and an optional
  category: Tops, Outerwear, Pants, Accessories, Footwear, or Any Category. It
  generates three profile-guided wardrobe reference images and can generate two
  more, up to five per interaction. Controls appear below each generated batch,
  and the user can finish after the first three. Images are inspiration only and
  are not shopping recommendations or profile inputs.
- `/remove` lists owned items ten per page with Previous and Next controls, then
  removes one after confirmation.
- `/resetprofile` clears all owned items from the active profile after confirmation.
- `/help` displays the command guide and photo tips.
- `/done` exits the current upload mode.

Telegram albums can contain at most ten photos per media group. If a user selects
more than ten, Telegram sends multiple groups and AURA processes each group as a
separate batch. Use one clear primary belonging per photo for the most reliable
analysis.

## Current Status

The local MVP is implemented and manually verified across `/add`, `/profile`,
`/check`, feedback buttons, `/suggestion`, `/remove`, and `/resetprofile`.
Initial V2 work adds fashion-presentation settings for suggestions and clearer,
item-specific `/check` explanations.
Automated backend and Telegram test suites cover the application and client
flows. Production deployment and Telegram-to-backend authentication remain
future work; see `docs/PROJECT_CONTEXT.md` for the complete status and roadmap.

The bot refreshes its Telegram command menu automatically when it starts.

The Telegram package is only a frontend adapter. It sends images and identity
headers to FastAPI and contains no prompts, scoring, profile, or persistence
logic.
