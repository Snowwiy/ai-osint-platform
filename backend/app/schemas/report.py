from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recon import JsonProperties

ReportType = Literal["executive", "technical"]
ReportStatus = Literal["pending", "generating", "ready", "failed"]
ReportDownloadFormat = Literal["html", "md"]


class ReportCreateRequest(BaseModel):
    report_type: ReportType = "technical"
    title: str | None = Field(default=None, min_length=1, max_length=255)


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    generated_by: uuid.UUID | None
    title: str | None
    report_type: ReportType
    report_format: str
    status: ReportStatus
    file_size_bytes: int | None
    report_metadata: JsonProperties
    error_message: str | None
    created_at: datetime


class ReportDetailResponse(ReportResponse):
    html_content: str | None
    markdown_content: str | None


class ReportListResponse(BaseModel):
    total: int
    items: list[ReportResponse]
