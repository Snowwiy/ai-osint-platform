from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RetentionPolicy = Literal[
    "indefinite",
    "30_days",
    "90_days",
    "180_days",
    "365_days",
    "archive_only",
]
FeatureFlagName = Literal[
    "enable_ai_analysis",
    "enable_report_exports",
    "enable_playbooks",
    "enable_bulk_actions",
    "enable_collaboration",
    "enable_audit_exports",
    "enable_advanced_dashboard",
    "enable_demo_mode",
]
ConfidentialityLabel = Literal[
    "Internal",
    "Client Confidential",
    "Restricted",
]


class GeneralSettings(BaseModel):
    platform_name: str = Field(default="RavenTech OSINT", min_length=2, max_length=120)
    deployment_label: str = Field(
        default="Internal Defensive Use",
        min_length=2,
        max_length=160,
    )
    support_contact: str = Field(default="", max_length=255)


class SecuritySettings(BaseModel):
    classification_banner: str = Field(
        default="Internal Use Only",
        max_length=160,
    )
    require_export_confirmation: bool = True


class RetentionSettings(BaseModel):
    investigations: RetentionPolicy = "indefinite"
    audit_logs: RetentionPolicy = "365_days"
    reports: RetentionPolicy = "365_days"
    notes: RetentionPolicy = "indefinite"
    tasks: RetentionPolicy = "indefinite"
    exports: RetentionPolicy = "365_days"


class ExportControlSettings(BaseModel):
    allow_pdf_export: bool = True
    allow_docx_export: bool = True
    allow_html_export: bool = True
    allow_markdown_export: bool = True
    watermark_exports: bool = False
    include_audit_summary: bool = True
    include_evidence_appendix: bool = True
    redact_analyst_names: bool = False
    redact_internal_notes: bool = False


class ReportBrandingSettings(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    report_title_prefix: str = Field(default="", max_length=120)
    logo_path: str = Field(default="", max_length=500)
    analyst_name: str = Field(default="", max_length=120)
    primary_color: str = "#7C3AED"
    secondary_color: str = "#111827"
    footer_text: str = Field(default="", max_length=240)
    confidentiality_label: ConfidentialityLabel = "Internal"

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def validate_hex_color(cls, value: str) -> str:
        clean = value.strip().upper()
        if len(clean) != 7 or not clean.startswith("#"):
            raise ValueError("color must use #RRGGBB format")
        try:
            int(clean[1:], 16)
        except ValueError as exc:
            raise ValueError("color must use #RRGGBB format") from exc
        return clean

    @field_validator("confidentiality_label", mode="before")
    @classmethod
    def normalize_confidentiality_label(cls, value: object) -> object:
        if value == "Internal Use Only":
            return "Internal"
        return value


class AuditPolicySettings(BaseModel):
    audit_login_events: bool = True
    audit_report_downloads: bool = True
    audit_recon_runs: bool = True
    audit_member_changes: bool = True
    audit_failed_permissions: bool = True
    audit_data_exports: bool = True


class FeatureFlagSettings(BaseModel):
    enable_ai_analysis: bool = True
    enable_report_exports: bool = True
    enable_playbooks: bool = True
    enable_bulk_actions: bool = True
    enable_collaboration: bool = True
    enable_audit_exports: bool = True
    enable_advanced_dashboard: bool = True
    enable_demo_mode: bool = False


class AdminSettingsResponse(BaseModel):
    id: uuid.UUID
    general: GeneralSettings
    security: SecuritySettings
    retention: RetentionSettings
    export_controls: ExportControlSettings
    report_branding: ReportBrandingSettings
    audit_policy: AuditPolicySettings
    feature_flags: FeatureFlagSettings
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AdminSettingsUpdate(BaseModel):
    general: GeneralSettings | None = None
    security: SecuritySettings | None = None
    export_controls: ExportControlSettings | None = None
    report_branding: ReportBrandingSettings | None = None
    audit_policy: AuditPolicySettings | None = None


class FeatureFlagUpdate(BaseModel):
    feature_flags: FeatureFlagSettings


class FeatureAvailabilityResponse(BaseModel):
    feature_flags: FeatureFlagSettings
    allowed_export_formats: list[Literal["pdf", "docx", "html", "md"]]


class RetentionUpdate(BaseModel):
    retention: RetentionSettings


class RetentionStatusResponse(BaseModel):
    retention: RetentionSettings
    eligible_for_archive: dict[str, int]
    destructive_deletion_enabled: Literal[False] = False


class AdminOverviewResponse(BaseModel):
    total_users: int = Field(ge=0)
    active_investigations: int = Field(ge=0)
    archived_investigations: int = Field(ge=0)
    reports_generated: int = Field(ge=0)
    audit_events: int = Field(ge=0)
    report_storage_bytes: int = Field(ge=0)
    feature_flags_enabled: int = Field(ge=0)
    retention_policies_configured: int = Field(ge=0)
    updated_at: datetime
