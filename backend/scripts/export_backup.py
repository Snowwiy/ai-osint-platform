from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db.session import AsyncSessionLocal

TABLES = (
    "investigations",
    "investigation_members",
    "targets",
    "recon_entities",
    "recon_relationships",
    "recon_enrichments",
    "threat_findings",
    "findings",
    "finding_evidence",
    "finding_tags",
    "knowledge_citations",
    "reports",
    "investigation_notes",
    "investigation_tasks",
    "investigation_evidence",
    "investigation_workflow_events",
    "audit_logs",
)
TABLES_WITH_INVESTIGATION_ID = {
    "audit_logs",
    "findings",
    "investigation_evidence",
    "investigation_members",
    "investigation_notes",
    "investigation_tasks",
    "investigation_workflow_events",
    "recon_enrichments",
    "recon_entities",
    "recon_relationships",
    "reports",
    "targets",
    "threat_findings",
}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Export RavenTech backup JSON.")
    parser.add_argument("--output", required=True, help="Backup output directory.")
    parser.add_argument("--investigation-id", help="Optional single investigation UUID.")
    args = parser.parse_args()

    investigation_id = uuid.UUID(args.investigation_id) if args.investigation_id else None
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir = output_dir / "report_files"
    report_dir.mkdir(exist_ok=True)

    manifest: dict[str, Any] = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "investigation_id": str(investigation_id) if investigation_id else None,
        "tables": {},
        "report_files": [],
    }

    async with AsyncSessionLocal() as db:
        for table in TABLES:
            rows = await _table_rows(db, table, investigation_id)
            manifest["tables"][table] = len(rows)
            (output_dir / f"{table}.json").write_text(
                json.dumps(rows, default=_json_default, indent=2),
                encoding="utf-8",
            )
        report_rows = await _table_rows(db, "reports", investigation_id)
        for report in report_rows:
            file_path = report.get("file_path")
            if not file_path:
                continue
            source = Path(str(file_path))
            if source.is_file():
                destination = report_dir / source.name
                shutil.copy2(source, destination)
                manifest["report_files"].append(destination.name)

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


async def _table_rows(
    db: Any,
    table: str,
    investigation_id: uuid.UUID | None,
) -> list[dict[str, Any]]:
    query = f"SELECT * FROM {table}"
    params: dict[str, Any] = {}
    if (
        investigation_id
        and table != "investigations"
        and table in TABLES_WITH_INVESTIGATION_ID
    ):
        query += " WHERE investigation_id = :investigation_id"
        params["investigation_id"] = investigation_id
    elif investigation_id:
        query += " WHERE id = :investigation_id"
        params["investigation_id"] = investigation_id
    result = await db.execute(text(query), params)
    return [dict(row._mapping) for row in result]


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date, uuid.UUID)):
        return str(value)
    return str(value)


if __name__ == "__main__":
    asyncio.run(main())
