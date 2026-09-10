from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.case_review import ReportApprovalStatus

ReportType = Literal[
    "executive",
    "technical",
    "remediation",
    "evidence_appendix",
    "compliance_mapping",
    "playbook_progress",
    "operational_dashboard",
]
ReportStatus = Literal["queued", "generating", "ready", "failed", "archived"]
ReportDownloadFormat = Literal["html", "md", "pdf", "docx"]
ReportLanguage = Literal["en", "es"]
ReportSection = Literal[
    "executive_summary",
    "scope",
    "authorization",
    "findings_summary",
    "severity_distribution",
    "threat_intelligence",
    "remediation_progress",
    "playbook_progress",
    "evidence_chains",
    "evidence_intelligence",
    "recurring_evidence",
    "related_investigations",
    "analyst_notes",
    "task_summary",
    "timeline_summary",
    "audit_summary",
    "framework_mapping",
    "appendix",
]
ReportSort = Literal[
    "newest",
    "oldest",
    "status",
    "report_type",
    "investigation",
]


class ReportCreateRequest(BaseModel):
    report_type: ReportType = "technical"
    title: str | None = Field(default=None, min_length=1, max_length=255)
    template_id: uuid.UUID | None = None
    output_format: ReportDownloadFormat = "html"
    language: ReportLanguage = "en"


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    generated_by: uuid.UUID | None
    template_id: uuid.UUID | None
    title: str | None
    report_type: ReportType
    report_format: ReportDownloadFormat
    status: ReportStatus
    progress_label: str | None
    file_size_bytes: int | None
    report_metadata: dict[str, object]
    error_message: str | None
    failure_reason: str | None
    retry_count: int
    generated_at: datetime | None
    archived_at: datetime | None
    approval_status: ReportApprovalStatus
    approval_submitted_by: uuid.UUID | None
    approval_submitted_at: datetime | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    approval_notes: str | None
    rejection_reason: str | None
    created_at: datetime


class ReportDetailResponse(ReportResponse):
    html_content: str | None
    markdown_content: str | None


class ReportListResponse(BaseModel):
    total: int
    items: list[ReportResponse]


class ReportTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=2000)
    report_type: ReportType
    sections: list[ReportSection] = Field(min_length=1, max_length=20)
    is_default: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def deduplicate_sections(self) -> ReportTemplateCreate:
        self.sections = list(dict.fromkeys(self.sections))
        return self


class ReportTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, min_length=2, max_length=2000)
    report_type: ReportType | None = None
    sections: list[ReportSection] | None = Field(
        default=None,
        min_length=1,
        max_length=20,
    )
    is_default: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def deduplicate_sections(self) -> ReportTemplateUpdate:
        if self.sections is not None:
            self.sections = list(dict.fromkeys(self.sections))
        return self


class ReportTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    report_type: ReportType
    sections: list[ReportSection]
    is_default: bool
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ReportTemplateListResponse(BaseModel):
    total: int
    items: list[ReportTemplateResponse]


class ReportQualityWarning(BaseModel):
    code: str
    message: str


class ReportQualityResponse(BaseModel):
    investigation_id: uuid.UUID
    report_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    warnings: list[ReportQualityWarning] = Field(default_factory=list)
    warning_count: int = Field(ge=0)
    ready_with_warnings: bool
    available_evidence: dict[str, int] = Field(default_factory=dict)
    missing_sections: list[str] = Field(default_factory=list)


class ReportingCenterItem(ReportResponse):
    investigation_title: str
    generated_by_name: str | None
    template_name: str | None


class ReportingCenterResponse(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[ReportingCenterItem]


class ReportBulkGenerateRequest(BaseModel):
    investigation_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    report_type: ReportType
    template_id: uuid.UUID | None = None
    output_format: ReportDownloadFormat = "html"
    language: ReportLanguage = "en"

    @model_validator(mode="after")
    def deduplicate_investigations(self) -> ReportBulkGenerateRequest:
        self.investigation_ids = list(dict.fromkeys(self.investigation_ids))
        return self


class ReportBulkResult(BaseModel):
    investigation_id: uuid.UUID
    report_id: uuid.UUID | None = None
    status: Literal["generated", "skipped", "failed"]
    detail: str


class ReportBulkGenerateResponse(BaseModel):
    generated: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)
    results: list[ReportBulkResult]


class ReportActionResponse(BaseModel):
    report: ReportResponse
    message: str
