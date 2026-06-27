from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReleaseMetadataResponse(BaseModel):
    app_name: str
    version: str
    release_channel: str
    build_date: str
    git_commit: str
    migration_version: str
    environment: str
    generated_at: datetime
