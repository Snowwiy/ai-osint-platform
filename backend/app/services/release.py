from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.release import ReleaseMetadataResponse


async def get_release_metadata(db: AsyncSession) -> ReleaseMetadataResponse:
    return ReleaseMetadataResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        release_channel=settings.APP_RELEASE_CHANNEL,
        build_date=settings.APP_BUILD_DATE,
        git_commit=_git_commit(),
        migration_version=await _migration_version(db),
        environment=settings.APP_ENVIRONMENT,
        generated_at=datetime.now(UTC),
    )


async def _migration_version(db: AsyncSession) -> str:
    try:
        value = (
            await db.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one_or_none()
        return str(value or "")
    except Exception:
        await db.rollback()
        return "unavailable"


def _git_commit() -> str:
    if settings.APP_GIT_COMMIT.strip():
        return settings.APP_GIT_COMMIT.strip()
    repo_root = Path(__file__).resolve().parents[3]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return "unavailable"
    commit = result.stdout.strip()
    return commit or "unavailable"
