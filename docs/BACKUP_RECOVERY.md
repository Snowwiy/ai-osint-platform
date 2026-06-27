# Backup And Recovery

This phase adds local backup utilities only. No cloud backup provider is used.

## JSON Export

Create a complete JSON export:

```bash
docker compose exec backend python scripts/export_backup.py --output /tmp/raventech-backup
```

Create an investigation-scoped export:

```bash
docker compose exec backend python scripts/export_backup.py \
  --output /tmp/investigation-backup \
  --investigation-id <uuid>
```

The export includes:

- investigations
- targets
- recon entities and relationships
- threat findings
- findings and evidence
- reports metadata
- notes, tasks, evidence metadata
- workflow events
- audit logs
- copied report files when `file_path` points to an existing file

## PostgreSQL Backup

For full database recovery, use PostgreSQL-native backup commands:

```bash
docker compose exec postgres pg_dump -U raventech -d raventech > raventech.sql
```

Restore into a clean database:

```bash
cat raventech.sql | docker compose exec -T postgres psql -U raventech -d raventech
docker compose exec backend alembic upgrade head
```

## Recovery Checklist

1. Stop write traffic.
2. Back up PostgreSQL and persistent volumes.
3. Restore PostgreSQL.
4. Restore `/data/reports` and `/data/chroma` volumes if needed.
5. Run `alembic upgrade head`.
6. Check `/health/ready`.
7. Verify audit, reports, recon, findings, and login.
