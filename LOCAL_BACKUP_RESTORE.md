# Local Backup, Restore, and Demo Reset

These procedures support the validated local Docker Compose mode only. They do
not deploy the application, configure DNS, migrate to Supabase, or handle
production infrastructure.

## Prerequisites

- Run commands from the repository root in PowerShell.
- Docker Desktop and the local Compose services must be available.
- Keep `.env` local. The scripts never copy `.env`, credentials, or provider
  configuration into an archive.
- Treat database and report backups as sensitive application data even though
  they contain no configuration secrets.
- Do not upload dumps or report archives to source control, public file-sharing
  links, issue attachments, or CI artifacts. `backups/` and generated report
  output are excluded by `.gitignore`.

## Create a PostgreSQL Backup

```powershell
./scripts/local/backup_db.ps1
```

The script runs `pg_dump` inside the `postgres` service, creates a timestamped
custom-format dump under `backups/local/`, verifies that it is non-empty, and
never replaces an existing file. The `backups/` directory is Git-ignored.

Include the named report-storage volume when needed:

```powershell
./scripts/local/backup_db.ps1 -IncludeReports
```

This adds a timestamped `tar.gz` archive of `/data/reports`. Report files are
derived exports, but preserving them can help reproduce a local demonstration.

## Restore Without Overwriting the Live Database

The restore script intentionally refuses `raventech`, `postgres`, and template
database names. It validates the dump and restores into a new database only:

```powershell
./scripts/local/restore_db.ps1 `
  -BackupPath ./backups/local/raventech-YYYYMMDD-HHMMSS-fff.dump
```

To choose a validation database name:

```powershell
./scripts/local/restore_db.ps1 `
  -BackupPath ./backups/local/raventech-YYYYMMDD-HHMMSS-fff.dump `
  -TargetDatabase raventech_restore_review
```

The command fails if the target already exists. It does not drop, truncate, or
rewire the live application database. Validate the restored database manually
before planning any separately reviewed cutover. If restoration fails after the
new database is created, it is retained for inspection rather than deleted.
Do not weaken these safeguards or rename a target to one of the refused live or
PostgreSQL system database names.

List restored databases without exposing credentials:

```powershell
docker compose exec -T postgres psql -U raventech -d postgres -c "\l"
```

Report archives are not restored automatically because extracting them into the
live named volume could overwrite exports. Inspect an archive in a separate
folder first; perform any later report-volume replacement only as an explicit,
separately reviewed maintenance action.

## Reset Synthetic Demo Data

Prepare or refresh demo data without clearing it:

```powershell
docker compose exec -T backend python -m scripts.seed_demo_data
```

The seed operation is idempotent and reuses matching synthetic IOC records.

For a clean reset, use the guarded wrapper. It creates a database safety backup
before clearing the fixed synthetic records and reseeding them:

```powershell
./scripts/local/reset_demo.ps1 -Confirmation RESET-DEMO
```

Only when a current backup already exists may an operator explicitly skip the
automatic safety backup:

```powershell
./scripts/local/reset_demo.ps1 -Confirmation RESET-DEMO -SkipSafetyBackup
```

The lower-level clear command also requires an exact confirmation phrase:

```powershell
docker compose exec -T backend python -m scripts.seed_demo_data `
  --clear --confirm-clear CLEAR-DEMO-DATA
```

Demo clear targets fixed synthetic records and the fixed demo investigation. It
does not select ordinary investigations by title, owner, date, or status.

## Verify After Backup, Restore, or Reset

```powershell
./scripts/local/check_local_health.ps1
docker compose exec -T backend alembic current
docker compose logs backend --tail=100
git status
```

See `LOCAL_HEALTH_REPAIR.md` for recovery guidance. Hosting, DNS, production
secrets, and Supabase migration remain deferred.
