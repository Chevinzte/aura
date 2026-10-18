# AURA Railway Deployment and Recovery

Last verified: 2026-10-18

## Purpose

This runbook describes AURA's public hackathon demonstration deployment. Railway
runs two independent services from the same GitHub repository:

| Service | Root directory | Public domain | Responsibility |
| --- | --- | --- | --- |
| `aura-backend` | `/backend` | Yes | FastAPI business logic and `/health` |
| `aura-telegram` | `/telegram-bot` | No | Telegram long-polling adapter |

Both services build from their local `Dockerfile`. Keep custom Railway build and
start commands empty so each Dockerfile remains the deployment source of truth.

## Prerequisites

- the GitHub repository is available to Railway;
- Supabase migrations are applied and the private `item-images` bucket exists;
- current Supabase, AI Lodge, OpenAI, and Telegram credentials are available;
- one random `AURA_INTERNAL_API_KEY` value of at least 32 characters has been
  generated for both services;
- any local Telegram worker has been stopped before the hosted worker starts.

Do not place credentials in this document, Dockerfiles, build arguments, commit
history, screenshots, or Railway public domains.

## Deploy the Backend

1. Create a Railway service from the GitHub repository and name it
   `aura-backend`.
2. Set its root directory to `/backend`.
3. Leave Build Command and Start Command empty. Railway should detect
   `backend/Dockerfile`.
4. Set the healthcheck path to `/health`.
5. Add the required runtime variables:

   ```text
   SUPABASE_URL
   SUPABASE_SECRET_KEY
   AURA_INTERNAL_API_KEY
   AURA_AI_BASE_URL
   AURA_AI_API_KEY
   ```

6. Add or confirm the model and validation settings:

   ```text
   AURA_AI_TIMEOUT_SECONDS=45
   AURA_VISION_MODEL=gemini-3.5-flash-lite
   AURA_EMBEDDING_MODEL=text-embedding-3-small
   AURA_EMBEDDING_DIMENSIONS=1536
   AURA_MAX_IMAGE_BYTES=10485760
   AURA_MIN_IMAGE_DIMENSION=256
   ```

7. To enable `/suggestion` image generation, add:

   ```text
   OPENAI_IMAGE_BASE_URL=https://api.openai.com/v1
   OPENAI_IMAGE_API_KEY
   OPENAI_IMAGE_MODEL=gpt-image-2.5-flare
   OPENAI_IMAGE_TIMEOUT_SECONDS=300
   OPENAI_IMAGE_QUALITY=low
   OPENAI_IMAGE_SIZE=1024x1024
   ```

8. To enable the landing-page demonstration button without publishing the bot
   address in GitHub, add this backend-only variable:

   ```text
   AURA_PUBLIC_TELEGRAM_URL=https://t.me/<your-bot-username>
   ```

9. Deploy and wait for the healthcheck to pass.
10. Generate a Railway public domain and verify:

   ```text
   https://<backend-domain>/health
   ```

   Expected response:

   ```json
   {"status":"ok"}
   ```

Railway supplies `PORT`; do not create a custom `PORT` variable.

## Deploy the Telegram Worker

1. Create a second Railway service from the same GitHub repository and name it
   `aura-telegram`.
2. Set its root directory to `/telegram-bot`.
3. Leave Build Command and Start Command empty so Railway detects
   `telegram-bot/Dockerfile`.
4. Do not configure a public domain or HTTP healthcheck for the polling worker.
5. Add:

   ```text
   TELEGRAM_BOT_TOKEN
   AURA_BACKEND_URL=https://<backend-domain>
   AURA_INTERNAL_API_KEY=<exact same value used by aura-backend>
   AURA_BACKEND_TIMEOUT_SECONDS=120
   ```

6. Use one replica. More than one long-polling worker with the same Telegram token
   can cause conflicting `getUpdates` requests.
7. Disable Railway Serverless sleeping for the worker. It continuously polls
   Telegram and is intended to remain active.
8. Deploy and inspect the logs for successful Telegram polling.

## Deployment Verification

1. Confirm the backend deployment reports healthy.
2. Open both services' live logs.
3. Send `/start`, `/profile`, and `/check` to the Telegram bot.
4. Confirm the Telegram service receives updates and sends responses.
5. Confirm corresponding `/v1` requests appear in the backend logs.
6. Verify there is no local Python process running AURA during this check.
7. Run one `/suggestion` before a public demonstration if image generation will be
   shown; this verifies the separately billed OpenAI provider configuration.

The hosted `/start`, `/profile`, and `/check` flows passed this verification on
2026-10-18.

## Normal Operation

- Keep both services at one replica for the demonstration.
- On a paid Railway plan, use an automatic restart policy appropriate for an
  always-on worker. Trial restart options are more limited.
- Watch Railway deployment state, usage, and logs before demonstrations.
- Watch AI Lodge and OpenAI quotas separately; they are not included in Railway
  usage credits.
- Avoid changing production variables immediately before a demonstration.
- Never start `restart-aura.ps1` locally while the hosted Telegram worker is live.

## Deploying a New Revision

1. Run both automated test suites locally.
2. Review staged changes and scan for credentials.
3. Commit and push to the connected deployment branch.
4. Railway builds each affected service from its root directory and Dockerfile.
5. Wait for backend health to pass, then inspect worker logs.
6. Repeat the Telegram verification steps.

Database migrations are not run by the service Dockerfiles. Apply and verify a
migration separately before deploying code that depends on it.

## Restart and Rollback

### Restart

- Restart `aura-backend` when configuration has changed or the API is unhealthy.
- Restart `aura-telegram` when polling stops or its token/backend settings change.
- After either restart, repeat `/start` and `/profile`; test an AI flow if the
  provider configuration changed.

### Rollback

1. Open the affected Railway service's deployment history.
2. Select the last known-good deployment and use Railway's rollback or redeploy
   action.
3. Confirm the variables still refer to the intended production services.
4. Verify `/health` for the backend and Telegram commands for the worker.
5. If a database migration caused incompatibility, follow the migration-specific
   recovery plan rather than deleting production records manually.

Rollback image availability depends on the Railway plan's image-retention window.
The Git commit remains the durable source for rebuilding an older revision.

## Data Recovery

Railway containers are disposable and do not hold AURA's durable user records or
uploaded item images. Durable data resides in Supabase PostgreSQL and private
Storage.

Use `backup-supabase.ps1` and `docs/BACKUP_AND_RECOVERY.md` for backup verification
and recovery. A code rollback does not roll back database contents or Storage
objects. Restore data only from a verified backup and preferably rehearse recovery
against a disposable Supabase project first.

## Known Demonstration Limits

- The Railway trial uses finite credits and has more limited restart behavior than
  paid plans.
- Production-grade alerting and centralized error reporting are not configured.
- Per-user and provider-aware AI rate limits are deferred.
- Supabase provider-managed point-in-time recovery is not enabled for the current
  project; the repository backup workflow remains important.
- Availability still depends on Telegram, Supabase, AI Lodge, OpenAI, and Railway.

These limits are acceptable for the hackathon demonstration but must be addressed
before broader public usage.
