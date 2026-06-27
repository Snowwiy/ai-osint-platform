# RavenTech OSINT Backup and Recovery

This guide describes defensive backup readiness for RavenTech OSINT. The
release-candidate operations center provides analyst-approved export and restore
validation. It does not schedule automatic backups or write restored data back
into the database.

## Backup Center

The Operations Center can export:

- Investigations
- Findings
- Reports metadata
- Report templates
- Admin settings
- Governance and retention configuration
- Knowledge metadata

Available formats:

- JSON
- ZIP

Exports intentionally exclude:

- Passwords
- JWTs
- API keys
- Provider secrets
- Raw `.env` values

## Creating a Backup

1. Sign in as an admin.
2. Open Admin → Operations.
3. Use Backup Readiness.
4. Export JSON or ZIP.
5. Store the file in an approved internal location.

Recommended timing:

- Before migrations
- Before changing governance settings
- Before report template changes
- Before production-style upgrades

## Restore Dry Run

The release candidate supports validation only.

1. Open Admin → Operations.
2. Select a backup JSON or ZIP file.
3. Run Validate dry run.
4. Review schema version, compatibility, corruption status, warnings, and record
   counts.

The dry run never overwrites existing data.

## Demo Data

Synthetic demo records can be reseeded or cleared independently of backup
exports:

```powershell
docker compose exec backend python scripts/seed_demo_data.py
docker compose exec backend python scripts/seed_demo_data.py --clear
```

Demo data is not authoritative recovery data. Treat it as portfolio/training
content only.

## Compatibility Checks

The restore validator checks:

- Backup schema version
- Required sections
- JSON parse integrity
- ZIP parse integrity
- Record count readability

Warnings do not always block restore planning. Errors indicate that a backup is
not currently compatible.

## Rollback Process

For production-style rollback:

1. Stop application traffic.
2. Preserve current database and report volume state.
3. Restore PostgreSQL using your database-level backup process.
4. Restore report volumes from the matching filesystem backup.
5. Run `alembic upgrade head` only after confirming the expected code version.
6. Validate `/health/ready`.
7. Validate Admin → Operations.

## Database-Level Backups

Use PostgreSQL-native backups for authoritative recovery:

```powershell
docker compose exec postgres pg_dump -U raventech raventech > raventech.sql
```

Restore with your approved operational runbook. Validate in staging before using
against production-style data.

## Report Export Preservation

Generated PDFs, DOCX files, HTML, and Markdown exports should be stored on a
persistent volume. Include that volume in filesystem backup processes.

## Known Limitations

- No scheduled backup jobs in RC1.
- No cloud backup target.
- No automatic restore writes.
- No overwrite restore operation.
- ZIP restore validation reads the contained backup JSON only.
