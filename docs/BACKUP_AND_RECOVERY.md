# Supabase Backup and Recovery

## Current Verification

Verified on 2026-10-18:

- the linked Supabase project is `ACTIVE_HEALTHY` in `ap-northeast-2`;
- PostgreSQL is running version `17.11.0.002`;
- the Supabase backup API reports PITR disabled and zero available platform
  restore points;
- a logical database snapshot was created with non-empty role, schema, and data
  files;
- the snapshot contains all nine AURA public-table data sections plus Supabase
  Auth and Storage metadata;
- all 87 objects in the private `item-images` bucket were downloaded;
- all 87 downloaded images are non-empty and have SHA-256 hashes in the Storage
  manifest.

The verified local snapshot is in `backups/verification-latest/`. The entire
`backups/` directory is ignored by Git because it contains private user data.

## Important Limitation

Supabase database backups do not contain Storage file contents. A database
restore can recover Storage metadata, but deleted image bytes must be restored
from a separate object backup.

The project currently has no Supabase-managed restore points. Until a paid plan
with daily backups or PITR is enabled, run the manual backup script after testing
sessions and before database or Storage changes. A backup stored only on the same
computer is not sufficient protection against device loss; copy completed backup
directories to an encrypted off-device location.

## Create a Backup

Prerequisites:

- Docker Desktop is running;
- `.env` contains `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
  `SUPABASE_DB_PASSWORD`, and `SUPABASE_ACCESS_TOKEN`;
- the repository remains linked to the intended Supabase project.

Run:

```powershell
.\backup-supabase.ps1
```

The script creates `backups/aura-<UTC timestamp>/` containing:

```text
backup-manifest.json
database/
  roles.sql
  schema.sql
  data.sql
storage/item-images/
  manifest.json
  users/.../original.jpg
```

The script fails if the destination is not empty, a database dump is empty, an
unexpected Storage path is returned, an image is empty, or remote and local
object counts differ. Neither secrets nor image bytes are committed to Git.

## Recovery Procedure

Never test a restore against the active AURA project. Create and link a disposable
Supabase project, then follow Supabase's official CLI restore order:

1. restore `roles.sql`;
2. restore `schema.sql`;
3. restore `data.sql`;
4. create or verify the private `item-images` bucket;
5. upload the backed-up `storage/item-images/users/` tree while preserving every
   object path;
6. compare restored object counts and SHA-256 hashes with `manifest.json`;
7. start AURA against the disposable project and test `/profile`, `/wardrobe`,
   stored-image display, and one `/check` flow.

Restoring the production project from a Supabase-managed backup causes downtime.
Choose the nearest restore point from before the incident and confirm the impact
before starting a restore.

Official references:

- <https://supabase.com/docs/guides/platform/backups>
- <https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore>
- <https://supabase.com/docs/guides/storage/management/download-objects>
