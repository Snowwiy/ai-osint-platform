export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type InvestigationStatus =
  | "intake"
  | "active"
  | "monitoring"
  | "remediation"
  | "validation"
  | "completed"
  | "archived";
export type InvestigationPriority = "low" | "medium" | "high" | "urgent";
export type PlatformUserRole = "admin" | "analyst";
export type AccountStatus = "active" | "pending" | "disabled" | "rejected";
export type NotificationSeverity = "info" | "success" | "warning" | "critical";
export type NotificationStatus = "unread" | "read" | "dismissed" | "archived";
export type InvestigationStage =
  | "intake"
  | "scoping"
  | "recon"
  | "analysis"
  | "remediation"
  | "validation"
  | "reporting"
  | "completed"
  | "archived";

export interface HealthResponse {
  status: "ok" | "degraded" | "error" | string;
  environment: string;
  checks: Record<
    string,
    {
      status: string;
      detail?: string;
      available?: boolean;
      current?: string;
      head?: string;
      paths?: Record<string, string>;
    }
  >;
}

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: "admin" | "analyst" | string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface AdminUser {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  role: PlatformUserRole | string;
  status: AccountStatus | string;
  account_status: AccountStatus | string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
  registration_source: string | null;
  approved_at: string | null;
  approved_by: string | null;
}

export interface AdminUserListResponse {
  total: number;
  limit: number;
  offset: number;
  items: AdminUser[];
}

export interface AdminUserFilters {
  role?: PlatformUserRole | "";
  status?: AccountStatus | "";
  search?: string;
  limit?: number;
  offset?: number;
}

export interface AdminUserActionResponse {
  user: AdminUser;
  message: string;
}

export interface RegistrationPolicyResponse {
  public_registration_enabled: boolean;
  requires_approval: boolean;
  invite_code_required: boolean;
  default_role: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  full_name?: string;
  invite_code?: string;
}

export interface RegisterResponse {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  account_status: "active" | "pending";
  message: string;
}

export interface NotificationItem {
  id: string;
  user_id: string | null;
  actor_user_id: string | null;
  investigation_id: string | null;
  engagement_id: string | null;
  entity_type: string;
  entity_id: string | null;
  notification_type: string;
  severity: NotificationSeverity | string;
  title: string;
  message: string;
  action_url: string | null;
  status: NotificationStatus | string;
  created_at: string;
  updated_at: string;
  read_at: string | null;
  dismissed_at: string | null;
  expires_at: string | null;
  metadata: Record<string, unknown>;
}

export interface NotificationListResponse {
  total: number;
  unread: number;
  limit: number;
  offset: number;
  items: NotificationItem[];
}

export interface NotificationUnreadCountResponse {
  unread: number;
}

export interface NotificationActionResponse {
  notification: NotificationItem;
  message: string;
}

export interface NotificationMarkAllReadResponse {
  updated: number;
  unread: number;
  message: string;
}

export interface NotificationFilters {
  status?: NotificationStatus | "";
  severity?: NotificationSeverity | "";
  notification_type?: string;
  investigation_id?: string;
  engagement_id?: string;
  limit?: number;
  offset?: number;
}

export type GlobalSearchType =
  | "investigation"
  | "engagement"
  | "finding"
  | "report"
  | "deliverable"
  | "notification"
  | "scope_item"
  | "user"
  | "closure"
  | "ioc"
  | "threat_object"
  | "evidence_summary";

export interface GlobalSearchFilters {
  q?: string;
  type?: GlobalSearchType | "";
  limit?: number;
  offset?: number;
  include_archived?: boolean;
  investigation_id?: string;
  engagement_id?: string;
}

export interface GlobalSearchResult {
  id: string;
  type: GlobalSearchType | string;
  title: string;
  subtitle: string | null;
  snippet: string | null;
  status: string | null;
  severity: string | null;
  route: string;
  created_at: string | null;
  updated_at: string | null;
  matched_fields: string[];
  metadata: Record<string, unknown>;
  score: number;
}

export interface GlobalSearchResponse {
  query: string;
  total: number;
  limit: number;
  offset: number;
  items: GlobalSearchResult[];
  result_types: string[];
}

export type SavedViewType =
  | "investigation_list"
  | "findings"
  | "reports"
  | "notifications"
  | "engagements"
  | "closure"
  | "search"
  | "dashboard";

export interface SavedView {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  view_type: SavedViewType | string;
  route: string;
  filters: Record<string, unknown>;
  sort: Record<string, unknown> | null;
  is_default: boolean;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface SavedViewListResponse {
  total: number;
  items: SavedView[];
}

export interface SavedViewCreateRequest {
  name: string;
  description?: string | null;
  view_type: SavedViewType;
  route: string;
  filters?: Record<string, unknown>;
  sort?: Record<string, unknown> | null;
  is_default?: boolean;
  is_pinned?: boolean;
}

export type SavedViewUpdateRequest = Partial<SavedViewCreateRequest>;

export type DataQualitySeverity = "info" | "warning" | "high" | "critical";
export type DataQualityStatus = "open" | "acknowledged" | "resolved" | "ignored";
export type DataQualityEntityType =
  | "investigation"
  | "engagement"
  | "scope_item"
  | "finding"
  | "evidence"
  | "report"
  | "deliverable"
  | "closure"
  | "notification"
  | "saved_view"
  | "user"
  | "audit_log"
  | "demo_data"
  | "system";

export interface DataQualityIssue {
  id: string;
  issue_type: string;
  severity: DataQualitySeverity | string;
  status: DataQualityStatus | string;
  entity_type: DataQualityEntityType | string;
  entity_id: string | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
  title: string;
  description: string;
  recommendation: string;
  action_url: string | null;
  detected_at: string;
  resolved_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DataQualityIssueFilters {
  severity?: DataQualitySeverity | "";
  status?: DataQualityStatus | "";
  issue_type?: string;
  entity_type?: DataQualityEntityType | "";
  investigation_id?: string;
  engagement_id?: string;
  limit?: number;
  offset?: number;
}

export interface DataQualityIssueListResponse {
  total: number;
  limit: number;
  offset: number;
  items: DataQualityIssue[];
}

export interface DataQualityOverviewResponse {
  total_issues: number;
  open_issues: number;
  critical_issues: number;
  high_issues: number;
  warning_issues: number;
  acknowledged_issues: number;
  resolved_issues: number;
  ignored_issues: number;
  by_entity_type: Record<string, number>;
  by_issue_type: Record<string, number>;
  last_scan_at: string | null;
  scan_status: "not_run" | "healthy" | "attention" | "critical" | string;
}

export interface DataQualityScanResponse {
  scanned_at: string;
  detected: number;
  created: number;
  existing: number;
  scan_limit: number;
  overview: DataQualityOverviewResponse;
}

export interface MaintenanceDryRunResponse {
  generated_at: string;
  would_detect: number;
  by_severity: Record<string, number>;
  by_entity_type: Record<string, number>;
  recommendations: string[];
  destructive_changes: boolean;
}

export interface StaleNotificationArchiveResponse {
  archived: number;
  older_than_days: number;
  message: string;
}

export type EngagementStatus = "draft" | "active" | "completed" | "archived";
export type AuthorizationStatus =
  | "not_provided"
  | "pending_review"
  | "approved"
  | "expired"
  | "revoked";
export type ScopeType =
  | "domain"
  | "subdomain"
  | "ip"
  | "cidr"
  | "email"
  | "username"
  | "organization"
  | "other";
export type ScopeStatus = "in_scope" | "out_of_scope" | "pending_review";
export type ScopeReviewStatus =
  | "not_reviewed"
  | "in_scope"
  | "out_of_scope"
  | "pending_review";
export type AuthorizationEvidenceType =
  | "contract"
  | "email_approval"
  | "statement_of_work"
  | "internal_authorization"
  | "other";

export interface Engagement {
  id: string;
  title: string;
  client_name: string;
  client_contact: string | null;
  description: string | null;
  status: EngagementStatus;
  authorization_status: AuthorizationStatus;
  start_date: string | null;
  end_date: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  linked_investigations_count: number;
  scope_counts: Record<ScopeStatus, number>;
}

export interface EngagementListResponse {
  total: number;
  items: Engagement[];
}

export interface EngagementCreateRequest {
  title: string;
  client_name: string;
  client_contact?: string | null;
  description?: string | null;
  status?: EngagementStatus;
  authorization_status?: AuthorizationStatus;
  start_date?: string | null;
  end_date?: string | null;
}

export type EngagementUpdateRequest = Partial<EngagementCreateRequest>;

export interface EngagementScopeItem {
  id: string;
  engagement_id: string;
  scope_type: ScopeType;
  value: string;
  description: string | null;
  status: ScopeStatus;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface EngagementScopeItemCreateRequest {
  scope_type: ScopeType;
  value: string;
  description?: string | null;
  status?: ScopeStatus;
}

export type EngagementScopeItemUpdateRequest =
  Partial<EngagementScopeItemCreateRequest>;

export interface AuthorizationEvidence {
  id: string;
  engagement_id: string;
  title: string;
  description: string | null;
  evidence_type: AuthorizationEvidenceType;
  reference: string | null;
  status: AuthorizationStatus;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuthorizationEvidenceCreateRequest {
  title: string;
  description?: string | null;
  evidence_type: AuthorizationEvidenceType;
  reference?: string | null;
  status?: AuthorizationStatus;
}

export type AuthorizationEvidenceUpdateRequest =
  Partial<AuthorizationEvidenceCreateRequest>;

export interface ScopeCheckRequest {
  value: string;
  scope_type?: ScopeType | null;
}

export interface ScopeCheckResponse {
  status: ScopeStatus;
  matched_scope_item: EngagementScopeItem | null;
  warning: string;
  recommended_action: string;
}

export interface AuditLogEntry {
  id: number;
  actor_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  investigation_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogListResponse {
  total: number;
  limit: number;
  offset: number;
  items: AuditLogEntry[];
}

export interface AuditLogFilters {
  action?: string;
  resource_type?: string;
  actor_id?: string;
  investigation_id?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export type RetentionPolicy =
  | "indefinite"
  | "30_days"
  | "90_days"
  | "180_days"
  | "365_days"
  | "archive_only";

export interface GeneralSettings {
  platform_name: string;
  deployment_label: string;
  support_contact: string;
}

export interface SecuritySettings {
  classification_banner: string;
  require_export_confirmation: boolean;
  require_engagement_for_new_investigations: boolean;
  warn_on_out_of_scope_targets: boolean;
  block_out_of_scope_targets: boolean;
  require_approved_authorization: boolean;
}

export interface RetentionSettings {
  investigations: RetentionPolicy;
  audit_logs: RetentionPolicy;
  reports: RetentionPolicy;
  notes: RetentionPolicy;
  tasks: RetentionPolicy;
  exports: RetentionPolicy;
}

export interface ExportControlSettings {
  allow_pdf_export: boolean;
  allow_docx_export: boolean;
  allow_html_export: boolean;
  allow_markdown_export: boolean;
  watermark_exports: boolean;
  include_audit_summary: boolean;
  include_evidence_appendix: boolean;
  redact_analyst_names: boolean;
  redact_internal_notes: boolean;
}

export interface ReportBrandingSettings {
  company_name: string;
  report_title_prefix: string;
  logo_path: string;
  analyst_name: string;
  primary_color: string;
  secondary_color: string;
  footer_text: string;
  confidentiality_label: "Internal" | "Client Confidential" | "Restricted";
}

export interface AuditPolicySettings {
  audit_login_events: boolean;
  audit_report_downloads: boolean;
  audit_recon_runs: boolean;
  audit_member_changes: boolean;
  audit_failed_permissions: boolean;
  audit_data_exports: boolean;
}

export interface FeatureFlagSettings {
  enable_ai_analysis: boolean;
  enable_report_exports: boolean;
  enable_playbooks: boolean;
  enable_bulk_actions: boolean;
  enable_collaboration: boolean;
  enable_audit_exports: boolean;
  enable_advanced_dashboard: boolean;
  enable_demo_mode: boolean;
}

export interface FeatureAvailabilityResponse {
  feature_flags: FeatureFlagSettings;
  allowed_export_formats: ReportFormat[];
}

export interface AdminSettingsResponse {
  id: string;
  general: GeneralSettings;
  security: SecuritySettings;
  retention: RetentionSettings;
  export_controls: ExportControlSettings;
  report_branding: ReportBrandingSettings;
  audit_policy: AuditPolicySettings;
  feature_flags: FeatureFlagSettings;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminSettingsUpdate {
  general?: GeneralSettings;
  security?: SecuritySettings;
  export_controls?: ExportControlSettings;
  report_branding?: ReportBrandingSettings;
  audit_policy?: AuditPolicySettings;
}

export interface RetentionStatusResponse {
  retention: RetentionSettings;
  eligible_for_archive: Record<string, number>;
  destructive_deletion_enabled: false;
}

export interface AdminOverviewResponse {
  total_users: number;
  active_investigations: number;
  archived_investigations: number;
  reports_generated: number;
  audit_events: number;
  report_storage_bytes: number;
  feature_flags_enabled: number;
  retention_policies_configured: number;
  updated_at: string;
}

export interface QaComponentStatus {
  status: string;
  detail: string;
}

export interface AdminQaStatusResponse {
  app_version: string;
  environment: string;
  generated_at: string;
  current_migration: string;
  head_migration: string;
  migration_status: string;
  feature_flags: Record<string, boolean>;
  report_templates_count: number;
  active_investigations_count: number;
  archived_investigations_count: number;
  audit_count: number;
  demo_mode_enabled: boolean;
  demo_investigation_ready: boolean;
  demo_investigation_id: string | null;
  components: Record<string, QaComponentStatus>;
  warnings: string[];
}

export type OperationalStatus = "healthy" | "degraded" | "unavailable";
export type ValidationStatus = "configured" | "missing" | "misconfigured";

export interface OperationsComponentStatus {
  status: OperationalStatus;
  detail: string;
  metadata: Record<string, string | boolean | number | null>;
}

export interface ReleaseInfo {
  app_name: string;
  version: string;
  release_channel: string;
  build_date: string;
  git_commit: string;
  build: string;
  environment: string;
  current_migration: string;
  head_migration: string;
  migration_status: string;
  database_version: string;
}

export interface StorageMetrics {
  investigations_count: number;
  findings_count: number;
  reports_count: number;
  templates_count: number;
  audit_events_count: number;
  knowledge_documents_count: number;
  report_storage_bytes: number;
  database_size_bytes: number;
}

export interface RecentOperationEvent {
  action: string;
  resource_type: string | null;
  created_at: string;
}

export interface OperationsStatusResponse {
  generated_at: string;
  status: OperationalStatus;
  uptime_seconds: number;
  release: ReleaseInfo;
  components: Record<string, OperationsComponentStatus>;
  storage: StorageMetrics;
  recent_operations: RecentOperationEvent[];
}

export interface EnvironmentValidationItem {
  name: string;
  scope: "backend" | "frontend" | "reports" | "ai" | "storage";
  status: ValidationStatus;
  required: boolean;
  detail: string;
}

export interface EnvironmentValidationResponse {
  generated_at: string;
  items: EnvironmentValidationItem[];
}

export interface RestoreValidationRequest {
  dry_run: boolean;
  backup?: Record<string, unknown> | null;
  archive_base64?: string | null;
}

export interface RestoreValidationResponse {
  dry_run: boolean;
  valid: boolean;
  schema_version: string | null;
  compatible: boolean;
  corruption_detected: boolean;
  record_counts: Record<string, number>;
  warnings: string[];
  errors: string[];
}

export interface DemoSeedResponse {
  enabled: boolean;
  ready: boolean;
  investigation_id: string | null;
  message: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string | null;
  token_type: string;
  expires_in: number;
  user?: Pick<UserProfile, "id" | "username" | "email" | "role"> | null;
}

export interface Investigation {
  id: string;
  title: string;
  description: string | null;
  status: InvestigationStatus;
  stage: InvestigationStage;
  owner_id: string;
  reviewer_id: string | null;
  engagement_id: string | null;
  authorization_statement: string;
  scope_definition: string | null;
  scope_review_status: ScopeReviewStatus;
  scope_notes: string | null;
  priority: InvestigationPriority;
  business_impact: string | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReadinessComponent {
  key: string;
  label: string;
  points: number;
  max_points: number;
  complete: boolean;
  detail: string;
}

export interface InvestigationReadinessResponse {
  investigation_id: string;
  score: number;
  category:
    | "Not Started"
    | "Scoping"
    | "Evidence Collection"
    | "Analysis Ready"
    | "Reporting Ready";
  stage: InvestigationStage;
  components: ReadinessComponent[];
  guidance: string[];
  generated_at: string;
}

export interface RiskScoreContributor {
  key: string;
  label: string;
  points: number;
  max_points: number;
  detail: string;
}

export interface InvestigationRiskScoreResponse {
  investigation_id: string;
  score: number;
  category:
    | "Low Risk"
    | "Moderate Risk"
    | "Elevated Risk"
    | "High Risk"
    | "Critical Risk";
  contributors: RiskScoreContributor[];
  generated_at: string;
}

export interface ExecutiveInvestigationSummaryResponse {
  investigation_id: string;
  title: string;
  objective: string;
  authorized_scope: string;
  stage: InvestigationStage;
  readiness_score: number;
  readiness_category: string;
  risk_score: number;
  risk_posture: InvestigationRiskScoreResponse["category"];
  status: string;
  key_findings: Array<{
    id: string;
    title: string;
    severity: Severity;
    status: string;
    risk_score: number;
    confidence_score: number;
  }>;
  unresolved_risk: string;
  recurring_issues: string[];
  notable_technologies: string[];
  business_impact: string;
  defensive_concerns: string[];
  remediation_urgency: string;
  confidence: number;
  generated_at: string;
}

export interface ExecutiveDashboardResponse {
  generated_at: string;
  active_investigations: number;
  high_risk_investigations: number;
  overdue_remediation: number;
  reporting_ready_investigations: number;
  investigations_without_remediation: number;
  investigations_missing_reports: number;
  recurring_infrastructure: Array<{ label: string; count: number }>;
  repeated_technologies: Array<{ label: string; count: number }>;
  repeated_findings: Array<{ label: string; count: number }>;
  repeated_high_risk_items: Array<{ label: string; count: number }>;
  analyst_workload: Array<{
    user_id: string;
    analyst_name: string;
    investigations: number;
    overdue_ownership: number;
    unresolved_findings: number;
  }>;
  detection_visibility: {
    mapped_findings: number;
    missing_coverage: number;
    coverage_percent: number;
    recurring_defensive_gaps: Array<{ label: string; count: number }>;
  };
  knowledge_usage: {
    most_referenced_frameworks: Array<{ label: string; count: number }>;
    common_defensive_concerns: Array<{ label: string; count: number }>;
  };
  threat_intelligence: {
    recurring_infrastructure: number;
    recurring_indicators: number;
    active_campaigns: number;
    attack_coverage: number;
    repeated_iocs: number;
    investigations_sharing_entities: number;
    high_confidence_iocs: number;
    high_confidence_observations: number;
    unresolved_correlated_findings: number;
    recent_intelligence_activity: Array<{ label: string; count: number }>;
  };
}

export interface ExecutivePostureResponse {
  generated_at: string;
  score: number;
  category: "Low" | "Medium" | "High" | "Critical";
  active_investigations: number;
  critical_findings: number;
  high_findings: number;
  open_remediation: number;
  overdue_remediation: number;
  contributing_factors: Array<{
    key: string;
    label: string;
    value: number;
    detail: string;
  }>;
}

export interface ExecutiveTrendPoint {
  date: string;
  findings: number;
  remediations_completed: number;
  investigations_created: number;
  reports_generated: number;
  risk_score: number;
}

export interface ExecutiveTrendsResponse {
  generated_at: string;
  points: ExecutiveTrendPoint[];
  summary: string;
}

export interface ExecutiveRecommendationItem {
  category: "Immediate" | "Short-Term" | "Long-Term";
  title: string;
  recommendation: string;
  evidence_refs: string[];
  related_findings: string[];
  related_investigations: string[];
}

export interface ExecutiveRecommendationsResponse {
  generated_at: string;
  items: ExecutiveRecommendationItem[];
}

export interface InvestigationListResponse {
  total: number;
  items: Investigation[];
}

export interface InvestigationPurgeImpact {
  investigation_id: string;
  title: string;
  status: InvestigationStatus;
  permanent_deletion_enabled: boolean;
  findings_count: number;
  notes_count: number;
  reports_count: number;
  tasks_count: number;
  evidence_count: number;
  members_count: number;
}

export type InvestigationMemberRole = "owner" | "admin" | "analyst" | "viewer";

export interface InvestigationMember {
  id: string;
  investigation_id: string;
  user_id: string;
  username: string;
  email: string;
  role: InvestigationMemberRole;
  invited_by: string | null;
  created_at: string;
  updated_at: string;
  last_activity_at: string | null;
}

export interface MemberAddRequest {
  user_id?: string | null;
  email?: string | null;
  username?: string | null;
  role: InvestigationMemberRole | "collaborator";
}

export interface MemberUpdateRequest {
  role?: InvestigationMemberRole | null;
  transfer_ownership?: boolean;
}

export interface InvestigationCreateRequest {
  title: string;
  description?: string | null;
  authorization_statement: string;
  scope_definition?: string | null;
  reviewer_id?: string | null;
  engagement_id?: string | null;
  scope_review_status?: ScopeReviewStatus;
  scope_notes?: string | null;
}

export interface InvestigationUpdateRequest {
  title?: string;
  description?: string | null;
  status?: InvestigationStatus;
  scope_definition?: string | null;
  engagement_id?: string | null;
  scope_review_status?: ScopeReviewStatus;
  scope_notes?: string | null;
}

export interface CollaborationUser {
  id: string;
  username: string;
  email: string;
}

export interface InvestigationOwnership {
  investigation_id: string;
  owner: CollaborationUser;
  assigned_analysts: CollaborationUser[];
  watchers: CollaborationUser[];
}

export interface InvestigationOwnershipUpdate {
  owner_id?: string | null;
  assigned_analyst_ids?: string[] | null;
  watcher_ids?: string[] | null;
  reason?: string | null;
}

export interface InvestigationHandoffRequest {
  new_owner_id: string;
  reason: string;
  context_transfer?: string | null;
  pending_work_summary?: string | null;
  unresolved_findings_summary?: string | null;
  remediation_status_summary?: string | null;
}

export interface InvestigationHandoff {
  id: string;
  investigation_id: string;
  previous_owner_id: string;
  new_owner_id: string;
  initiated_by: string | null;
  reason: string;
  context_transfer: string | null;
  pending_work_summary: string | null;
  unresolved_findings_summary: string | null;
  remediation_status_summary: string | null;
  created_at: string;
}

export type EscalationLevel =
  | "informational"
  | "analyst_review"
  | "senior_review"
  | "urgent_review";

export interface InvestigationEscalation {
  id: string;
  investigation_id: string;
  level: EscalationLevel;
  reason: string;
  created_by: string | null;
  created_at: string;
}

export interface CollaborationDashboardInvestigation {
  id: string;
  title: string;
  state: InvestigationStatus;
  priority: InvestigationPriority;
  scope: "owned" | "assigned" | "watching";
  owner_id: string;
  open_tasks: number;
  blocked_tasks: number;
  overdue_tasks: number;
  urgent_findings: number;
  escalation_count: number;
  updated_at: string;
}

export interface CollaborationDashboardResponse {
  generated_at: string;
  owned: CollaborationDashboardInvestigation[];
  assigned: CollaborationDashboardInvestigation[];
  watching: CollaborationDashboardInvestigation[];
  needs_attention: CollaborationDashboardInvestigation[];
  recent_coordination: Array<{
    id: number;
    investigation_id: string;
    investigation_title: string;
    actor_id: string | null;
    action: string;
    timestamp: string;
    metadata: Record<string, unknown>;
  }>;
}

export type TriageCategory =
  | "low_attention"
  | "monitor"
  | "active_review"
  | "urgent_review";

export type QueueStatusFilter =
  | "intake"
  | "active"
  | "monitoring"
  | "remediation"
  | "validation"
  | "completed"
  | "archived";

export type QueueSort =
  | "newest"
  | "oldest"
  | "highest_risk"
  | "overdue"
  | "most_findings"
  | "least_activity";

export type RiskFilter = "low" | "medium" | "high" | "critical";

export interface OperationsSignal {
  value: string;
  count: number;
  investigation_count: number;
}

export interface DashboardOperationsInvestigation {
  id: string;
  title: string;
  status: InvestigationStatus;
  priority: InvestigationPriority;
  risk_score: number;
  triage_score: number;
  triage_category: TriageCategory;
  findings_count: number;
  overdue_tasks: number;
  pinned: boolean;
  updated_at: string;
}

export interface DashboardOverviewResponse {
  generated_at: string;
  investigations: {
    total: number;
    active: number;
    archived: number;
    urgent: number;
    overdue: number;
  };
  findings: {
    total: number;
    unresolved: number;
    by_severity: Record<Severity, number>;
  };
  remediation: {
    open_tasks: number;
    overdue_tasks: number;
    blocked_tasks: number;
    completed_tasks: number;
    completion_percent: number;
  };
  analyst_activity: {
    recent_actions: number;
    investigations_touched: number;
    notes_created: number;
    remediation_completed: number;
  };
  infrastructure_signals: {
    recurring_technologies: OperationsSignal[];
    repeated_findings: OperationsSignal[];
    recurring_domains: OperationsSignal[];
    recurring_ips: OperationsSignal[];
  };
  pinned_investigations: DashboardOperationsInvestigation[];
  recent_investigations: DashboardOperationsInvestigation[];
}

export interface DashboardHighlightItem {
  investigation_id: string;
  title: string;
  kind:
    | "needs_attention"
    | "overdue_remediation"
    | "without_findings"
    | "recently_archived"
    | "recent_activity";
  detail: string;
  severity: Severity;
  occurred_at: string;
}

export interface DashboardHighlightsResponse {
  generated_at: string;
  needs_attention: DashboardHighlightItem[];
  overdue_remediation: DashboardHighlightItem[];
  without_findings: DashboardHighlightItem[];
  recently_archived: DashboardHighlightItem[];
  recent_activity: DashboardHighlightItem[];
}

export interface InvestigationTriageItem {
  investigation_id: string;
  title: string;
  score: number;
  category: TriageCategory;
  components: {
    severity: number;
    unresolved: number;
    remediation: number;
    overdue_tasks: number;
    recurring_evidence: number;
    priority: number;
  };
  reasons: string[];
}

export interface DashboardTriageResponse {
  generated_at: string;
  total: number;
  items: InvestigationTriageItem[];
}

export interface InvestigationQueueItem {
  id: string;
  title: string;
  status: InvestigationStatus;
  priority: InvestigationPriority;
  owner_id: string;
  reviewer_id: string | null;
  assigned_analyst_ids: string[];
  due_date: string | null;
  overdue: boolean;
  risk_score: number;
  risk_level: RiskFilter;
  triage_score: number;
  triage_category: TriageCategory;
  findings_count: number;
  unresolved_findings: number;
  open_tasks: number;
  overdue_tasks: number;
  tags: Array<{ id: string; name: string; color: string }>;
  pinned: boolean;
  last_activity_at: string;
  created_at: string;
  updated_at: string;
}

export interface InvestigationQueueResponse {
  total: number;
  skip: number;
  limit: number;
  items: InvestigationQueueItem[];
}

export interface InvestigationQueueFilters {
  status?: QueueStatusFilter;
  priority?: InvestigationPriority;
  assigned_analyst?: string;
  tag?: string;
  risk_level?: RiskFilter;
  sort?: QueueSort;
  skip?: number;
  limit?: number;
}

export type InvestigationBulkAction =
  | "assign_owner"
  | "assign_reviewer"
  | "update_priority"
  | "update_tags"
  | "archive"
  | "change_status"
  | "add_playbook"
  | "generate_summary";

export interface InvestigationBulkRequest {
  investigation_ids: string[];
  action: InvestigationBulkAction;
  owner_id?: string | null;
  reviewer_id?: string | null;
  priority?: InvestigationPriority | null;
  tag_ids?: string[] | null;
  status?: InvestigationStatus | null;
  playbook_id?: string | null;
}

export interface InvestigationBulkResponse {
  action: InvestigationBulkAction;
  requested: number;
  succeeded: number;
  failed: number;
  results: Array<{
    investigation_id: string;
    success: boolean;
    detail: string;
  }>;
}

export interface DashboardTimelineResponse {
  total: number;
  limit: number;
  offset: number;
  items: Array<{
    id: number;
    timestamp: string;
    actor_id: string | null;
    actor_name: string | null;
    investigation_id: string | null;
    investigation_title: string | null;
    event_type: string;
    resource_type: string | null;
    resource_id: string | null;
    metadata: Record<string, unknown>;
  }>;
}

export interface AnalystWorkloadResponse {
  generated_at: string;
  total: number;
  items: Array<{
    user_id: string;
    username: string;
    email: string;
    active_investigations: number;
    overdue_remediation: number;
    findings_assigned: number;
    notes_added_30d: number;
    remediations_completed_30d: number;
    previous_30d_completed: number;
    completion_trend: "up" | "steady" | "down";
  }>;
}

export type TargetType = "domain" | "ip" | "url";

export interface Target {
  id: string;
  investigation_id: string;
  target_type: TargetType;
  target_value: string;
  label: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
}

export interface TargetListResponse {
  total: number;
  items: Target[];
}

export interface TargetCreateRequest {
  investigation_id: string;
  target_type: TargetType;
  target_value: string;
  label?: string | null;
  notes?: string | null;
}

export interface ReconResponse {
  investigation_id: string | null;
  enrichment_id: string | null;
  target_type: TargetType;
  target_value: string;
  status: "completed" | "partial" | "failed";
  entities: NormalizedEntity[];
  relationships: NormalizedRelationship[];
  errors: ReconError[];
  dns?: unknown;
  rdap?: unknown;
  certificates?: unknown;
  ip?: unknown;
  http?: unknown;
}

export interface NormalizedEntity {
  entity_type: string;
  value: string;
  display_name: string | null;
  properties: Record<string, unknown>;
  source: string | null;
}

export interface NormalizedRelationship {
  relationship_type: string;
  source_type: string;
  source_value: string;
  target_type: string;
  target_value: string;
  properties: Record<string, unknown>;
  source: string | null;
}

export interface ReconError {
  source: string;
  message: string;
}

export interface GraphNode {
  id: string;
  entity_type: string;
  value: string;
  display_name: string | null;
  properties: Record<string, unknown>;
  source: string | null;
  first_seen: string;
  last_seen: string;
}

export interface GraphEdge {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: string;
  properties: Record<string, unknown>;
  source: string | null;
  created_at: string;
}

export interface InvestigationGraphResponse {
  investigation_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  risk_summary: {
    total_entities: number;
    entity_counts: Record<string, number>;
    risk_level: string;
    signals: string[];
  };
  timeline: unknown[];
  findings: GraphFinding[];
  finding_edges: unknown[];
}

export interface GraphFinding {
  id: string;
  title: string;
  severity: Severity;
  status: string;
  risk_score: number;
  source: string;
  linked_entity_ids: string[];
  threat_finding_ids: string[];
}

export interface Finding {
  id: string;
  investigation_id: string;
  title: string;
  description: string;
  severity: Severity;
  confidence_score: number;
  risk_score: number;
  source: string;
  status: string;
  assigned_to: string | null;
  reviewed_by: string | null;
  review_notes: string | null;
  remediation_notes: string | null;
  remediation_status: RemediationStatus;
  remediation_owner: string | null;
  remediation_due_date: string | null;
  verification_notes: string | null;
  verified_by: string | null;
  verified_at: string | null;
  validation_notes: string | null;
  validation_status: RemediationValidationStatus;
  validation_owner: string | null;
  validation_failure_reason: string | null;
  confidence_reasoning: string | null;
  evidence_summary: string | null;
  review_history: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
  evidence: FindingEvidence[];
  tags: string[];
  summary: string;
  evidence_chain: FindingEvidenceChainItem[];
  affected_targets: string[];
  framework_mappings: FindingFrameworkMapping[];
  remediation_guidance: string[];
  analyst_notes: string[];
  references: string[];
}

export type FindingStatus =
  | "new"
  | "under_review"
  | "validated"
  | "accepted_risk"
  | "mitigated"
  | "false_positive"
  | "archived";

export type RemediationStatus =
  | "not_started"
  | "validating"
  | "remediation_planned"
  | "in_progress"
  | "pending_verification"
  | "remediated"
  | "accepted_risk"
  | "false_positive";

export type RemediationValidationStatus =
  | "not_validated"
  | "validation_pending"
  | "validated"
  | "validation_failed"
  | "accepted_risk";

export type PlaybookRunStatus =
  | "open"
  | "in_progress"
  | "blocked"
  | "completed"
  | "cancelled";

export type PlaybookRunStepStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "skipped";

export interface PlaybookStep {
  id: string;
  playbook_id: string;
  order_index: number;
  title: string;
  description: string;
  expected_output: string | null;
  step_type: string;
  required: boolean;
  created_at: string;
  updated_at: string;
}

export interface DefensivePlaybook {
  id: string;
  name: string;
  description: string;
  category: string;
  severity: Severity;
  framework: string | null;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  steps: PlaybookStep[];
}

export interface FindingPlaybookRecommendation {
  playbook: DefensivePlaybook;
  reason: string;
  recommended: boolean;
}

export interface PlaybookRunStep {
  id: string;
  playbook_run_id: string;
  playbook_step_id: string;
  status: PlaybookRunStepStatus;
  analyst_note: string | null;
  completed_by: string | null;
  completed_at: string | null;
  step: PlaybookStep;
}

export interface PlaybookRun {
  id: string;
  investigation_id: string;
  finding_id: string;
  finding_title: string;
  playbook_id: string;
  playbook_name: string;
  status: PlaybookRunStatus;
  started_by: string | null;
  completed_by: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  steps: PlaybookRunStep[];
}

export interface FindingRemediationUpdate {
  remediation_status: RemediationStatus;
  remediation_owner?: string | null;
  remediation_due_date?: string | null;
  remediation_notes?: string | null;
  verification_notes?: string | null;
  verified_by?: string | null;
}

export interface FindingRemediationResponse {
  finding_id: string;
  investigation_id: string;
  remediation_status: RemediationStatus;
  remediation_owner: string | null;
  remediation_due_date: string | null;
  remediation_notes: string | null;
  verification_notes: string | null;
  verified_by: string | null;
  verified_at: string | null;
}

export interface FindingEvidence {
  id: string;
  finding_id: string;
  recon_entity_id: string | null;
  threat_finding_id: string | null;
  evidence_type: string;
  source: string;
  description: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface FindingEvidenceChainItem {
  id: string;
  source: string;
  evidence_type: string;
  description: string;
  recon_entity_id: string | null;
  threat_finding_id: string | null;
  created_at: string;
}

export interface FindingFrameworkMapping {
  framework: string;
  control: string;
  rationale: string;
  citation_ids: string[];
  confidence: number | null;
}

export interface MitreDefensiveMapping {
  technique_id: string;
  name: string;
  tactic: string;
  defensive_explanation: string;
  why_mapping_exists: string;
  references: string[];
}

export interface SigmaDetectionReference {
  id: string;
  title: string;
  description: string;
  log_source: string;
  tags: string[];
  detection_idea: string;
  defensive_explanation: string;
  references: string[];
}

export interface YaraDefensiveReference {
  id: string;
  title: string;
  family: string;
  category: string;
  why_it_matters: string;
  defensive_detection_context: string;
  analyst_explanation: string;
  references: string[];
}

export interface FindingDetectionRecommendation {
  finding_id: string;
  finding_title: string;
  severity: Severity;
  why_this_matters: string;
  monitoring_recommendations: string[];
  logging_recommendations: string[];
  remediation_guidance: string[];
  mitre_mappings: MitreDefensiveMapping[];
  sigma_references: SigmaDetectionReference[];
  yara_references: YaraDefensiveReference[];
  references: string[];
}

export interface InvestigationRecommendationsResponse {
  investigation_id: string;
  generated_at: string;
  total_findings: number;
  recommendations: FindingDetectionRecommendation[];
  recommended_next_steps: string[];
}

export interface InvestigationCoverageResponse {
  investigation_id: string;
  generated_at: string;
  total_findings: number;
  mapped_findings: number;
  detection_guidance_available: number;
  missing_coverage: number;
  coverage_percent: number;
  category: "weak" | "partial" | "moderate" | "strong";
  framework_counts: Record<string, number>;
  missing_defensive_visibility: string[];
  monitoring_recommendations: string[];
  findings: Array<{
    finding_id: string;
    title: string;
    mapped: boolean;
    guidance_available: boolean;
    frameworks: string[];
    missing_visibility: string[];
  }>;
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  event_type: string;
  severity: Severity;
  source: string;
  title: string;
  summary: string;
  related_entity_ids: string[];
  related_finding_ids: string[];
  confidence: number;
  metadata: Record<string, unknown>;
}

export interface TimelineResponse {
  investigation_id: string;
  total: number;
  events: TimelineEvent[];
}

export interface CorrelationNode {
  id: string;
  node_type: string;
  label: string;
  source: string;
  entity_id: string | null;
  finding_id: string | null;
  report_id: string | null;
  metadata: Record<string, unknown>;
}

export interface CorrelationEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  correlation_type: string;
  confidence: "low" | "medium" | "high";
  summary: string;
  evidence_count: number;
  metadata: Record<string, unknown>;
}

export interface CorrelationResponse {
  investigation_id: string;
  total_nodes: number;
  total_edges: number;
  nodes: CorrelationNode[];
  edges: CorrelationEdge[];
}

export type IOCType =
  | "ip"
  | "domain"
  | "subdomain"
  | "url"
  | "email"
  | "hash"
  | "asn"
  | "certificate"
  | "hostname"
  | "technology";

export type IOCConfidence = "low" | "medium" | "high";

export interface IOCSummary {
  id: string;
  value: string;
  type: IOCType;
  source: string;
  confidence: IOCConfidence;
  confidence_score: number;
  confidence_reason: string;
  first_seen: string;
  last_seen: string;
  investigation_count: number;
  observation_count: number;
  related_findings: number;
  related_entities: number;
  tags: string[];
  notes: string | null;
}

export interface IOCInvestigationReference {
  investigation_id: string;
  investigation_title: string;
  first_seen: string;
  last_seen: string;
  recon_entity_id: string | null;
  finding_count: number;
}

export interface IOCFindingReference {
  id: string;
  investigation_id: string;
  title: string;
  severity: Severity;
  status: string;
  remediation_status: string;
}

export interface IOCEvidenceRelationship {
  relationship_type:
    | "finding"
    | "report"
    | "remediation"
    | "timeline"
    | "playbook"
    | "recon_entity";
  resource_id: string;
  title: string;
  investigation_id: string;
  why_this_matters: string;
}

export interface IOCDetail extends IOCSummary {
  investigations: IOCInvestigationReference[];
  findings: IOCFindingReference[];
  evidence_relationships: IOCEvidenceRelationship[];
  defensive_guidance: string[];
}

export interface IOCListResponse {
  total: number;
  limit: number;
  offset: number;
  items: IOCSummary[];
}

export interface IOCCorrelation {
  ioc: IOCSummary;
  category: string;
  investigations: IOCInvestigationReference[];
  related_findings: IOCFindingReference[];
  severity_distribution: Record<Severity, number>;
}

export interface IOCCorrelationResponse {
  generated_at: string;
  total: number;
  items: IOCCorrelation[];
}

export type IntelligenceConfidence = "Low" | "Medium" | "High" | "Very High";
export type InvestigationPrioritySuggestion =
  | "Low"
  | "Medium"
  | "High"
  | "Critical";

export interface IntelligenceInvestigationReference {
  investigation_id: string;
  investigation_title: string;
  status: string;
  priority: string;
  resource_id: string | null;
}

export interface EvidenceIntelligenceItem {
  id: string;
  item_type: string;
  value: string;
  occurrence_count: number;
  investigation_count: number;
  source_count: number;
  first_seen: string | null;
  last_seen: string | null;
  confidence: IntelligenceConfidence;
  confidence_reasons: string[];
  related_investigations: IntelligenceInvestigationReference[];
  related_findings: string[];
  related_reports: string[];
}

export interface EvidenceIntelligenceOverviewResponse {
  generated_at: string;
  total_items: number;
  recurring_domains: EvidenceIntelligenceItem[];
  recurring_ips: EvidenceIntelligenceItem[];
  recurring_technologies: EvidenceIntelligenceItem[];
  recurring_findings: EvidenceIntelligenceItem[];
  recurring_framework_mappings: EvidenceIntelligenceItem[];
  recurring_evidence_chains: EvidenceIntelligenceItem[];
  repeated_high_risk_items: EvidenceIntelligenceItem[];
}

export interface EvidenceIntelligenceEvidenceResponse {
  generated_at: string;
  total: number;
  items: EvidenceIntelligenceItem[];
}

export interface EvidenceIntelligencePriorityItem {
  investigation_id: string;
  investigation_title: string;
  current_priority: string;
  suggested_priority: InvestigationPrioritySuggestion;
  score: number;
  reasons: string[];
  metrics: Record<string, number>;
}

export interface EvidenceIntelligencePriorityResponse {
  generated_at: string;
  total: number;
  items: EvidenceIntelligencePriorityItem[];
}

export interface EvidenceIntelligenceTimelineEvent {
  id: string;
  timestamp: string;
  event_type:
    | "first_observed"
    | "repeated_observation"
    | "remediation_completed"
    | "recurrence_after_remediation";
  item_type: string;
  value: string;
  title: string;
  summary: string;
  confidence: IntelligenceConfidence;
  investigation_id: string | null;
  investigation_title: string | null;
}

export interface EvidenceIntelligenceTimelineResponse {
  generated_at: string;
  total: number;
  items: EvidenceIntelligenceTimelineEvent[];
}

export interface EvidenceIOCIntelligenceItem {
  ioc_id: string;
  value: string;
  type: string;
  confidence: string;
  investigation_count: number;
  frequency: number;
  first_seen: string;
  last_seen: string;
  seen_in_investigations: IntelligenceInvestigationReference[];
  seen_in_findings: string[];
  seen_in_reports: string[];
}

export interface EvidenceIntelligenceIOCResponse {
  generated_at: string;
  total: number;
  items: EvidenceIOCIntelligenceItem[];
}

export type ThreatWorkspaceConfidence = "Low" | "Medium" | "High" | "Confirmed";

export interface ThreatInvestigationReference {
  investigation_id: string;
  investigation_title: string;
  status: string;
  priority: string;
  first_seen: string | null;
  last_seen: string | null;
}

export interface ThreatIndicatorSummary {
  id: string;
  value: string;
  type: string;
  source: string;
  confidence: ThreatWorkspaceConfidence;
  confidence_reason: string;
  first_seen: string;
  last_seen: string;
  occurrence_count: number;
  investigation_count: number;
  findings_count: number;
  reports_count: number;
  investigations: ThreatInvestigationReference[];
  tags: string[];
}

export interface ThreatCampaignSummary {
  id: string;
  name: string;
  description: string | null;
  status: string;
  confidence: ThreatWorkspaceConfidence;
  first_observed: string | null;
  last_observed: string | null;
  indicator_count: number;
  finding_count: number;
  investigation_count: number;
  technique_count: number;
}

export interface ThreatGroupSummary {
  id: string;
  name: string;
  aliases: string[];
  description: string | null;
  confidence: ThreatWorkspaceConfidence;
  notes: string | null;
  campaign_count: number;
  indicator_count: number;
  technique_count: number;
}

export interface ThreatTechniqueSummary {
  id: string;
  technique_id: string;
  name: string;
  tactic: string | null;
  procedure: string | null;
  confidence: ThreatWorkspaceConfidence;
  mapped_findings: number;
  mapped_campaigns: number;
  mapped_groups: number;
  coverage_count: number;
  why_mapping_exists: string;
}

export interface ThreatInfrastructureSummary {
  id: string;
  infrastructure_type: string;
  value: string;
  confidence: ThreatWorkspaceConfidence;
  first_seen: string | null;
  last_seen: string | null;
  occurrence_count: number;
  investigation_count: number;
  investigations: ThreatInvestigationReference[];
}

export interface ThreatTimelineEvent {
  id: string;
  timestamp: string;
  event_type:
    | "indicator_observed"
    | "indicator_repeated"
    | "campaign_created"
    | "campaign_updated"
    | "group_linked"
    | "technique_mapped"
    | "remediation_completed";
  title: string;
  summary: string;
  confidence: ThreatWorkspaceConfidence;
  investigation_id: string | null;
  investigation_title: string | null;
}

export interface ThreatOverviewResponse {
  generated_at: string;
  indicator_count: number;
  active_campaigns: number;
  threat_group_count: number;
  technique_count: number;
  recurring_infrastructure_count: number;
  high_confidence_observations: number;
  attack_coverage: number;
  recent_activity: ThreatTimelineEvent[];
}

export interface ThreatIndicatorListResponse {
  generated_at: string;
  total: number;
  items: ThreatIndicatorSummary[];
}

export interface ThreatCampaignListResponse {
  generated_at: string;
  total: number;
  items: ThreatCampaignSummary[];
}

export interface ThreatGroupListResponse {
  generated_at: string;
  total: number;
  items: ThreatGroupSummary[];
}

export interface ThreatTechniqueListResponse {
  generated_at: string;
  total: number;
  items: ThreatTechniqueSummary[];
}

export interface ThreatInfrastructureResponse {
  generated_at: string;
  total: number;
  items: ThreatInfrastructureSummary[];
}

export interface ThreatTimelineResponse {
  generated_at: string;
  total: number;
  items: ThreatTimelineEvent[];
}

export interface InvestigationPrioritizationResponse {
  investigation_id: string;
  generated_at: string;
  score: number;
  category:
    | "Low Priority"
    | "Moderate Priority"
    | "High Priority"
    | "Immediate Review";
  explanation: string;
  contributors: Record<string, number>;
  prioritized_iocs: Array<{
    ioc: IOCSummary;
    score: number;
    category: string;
    reasons: string[];
  }>;
}

export interface IOCGuidanceCard {
  id: string;
  title: string;
  applies_to: string[];
  monitoring_guidance: string[];
  logging_recommendations: string[];
  mitre_relevance: string[];
  sigma_references: string[];
  remediation_guidance: string[];
  why_this_matters: string;
}

export interface IOCGuidanceResponse {
  total: number;
  items: IOCGuidanceCard[];
}

export type CrossInvestigationSignalType =
  | "domain"
  | "subdomain"
  | "ip"
  | "technology"
  | "finding"
  | "evidence"
  | "framework";

export interface CrossInvestigationCorrelationResponse {
  generated_at: string;
  total_signals: number;
  signals: Array<{
    signal_type: CrossInvestigationSignalType;
    value: string;
    investigation_count: number;
    confidence: "low" | "medium" | "high";
    investigations: Array<{
      investigation_id: string;
      investigation_title: string;
      resource_id: string | null;
    }>;
  }>;
}

export type ReportType =
  | "executive"
  | "technical"
  | "remediation"
  | "evidence_appendix"
  | "compliance_mapping"
  | "playbook_progress"
  | "operational_dashboard";
export type ReportFormat = "html" | "md" | "pdf" | "docx";
export type ReportStatus =
  | "queued"
  | "generating"
  | "ready"
  | "failed"
  | "archived";
export type ReportApprovalStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "archived";
export type ReportSort =
  | "newest"
  | "oldest"
  | "status"
  | "report_type"
  | "investigation";
export type ReportSection =
  | "executive_summary"
  | "scope"
  | "authorization"
  | "findings_summary"
  | "severity_distribution"
  | "threat_intelligence"
  | "remediation_progress"
  | "playbook_progress"
  | "evidence_chains"
  | "evidence_intelligence"
  | "recurring_evidence"
  | "related_investigations"
  | "analyst_notes"
  | "task_summary"
  | "timeline_summary"
  | "audit_summary"
  | "framework_mapping"
  | "appendix";

export interface ReportCreateRequest {
  report_type: ReportType;
  title?: string | null;
  template_id?: string | null;
  output_format?: ReportFormat;
}

export interface ReportSummary {
  id: string;
  investigation_id: string;
  generated_by: string | null;
  template_id: string | null;
  title: string | null;
  report_type: ReportType;
  report_format: ReportFormat;
  status: ReportStatus;
  progress_label: string | null;
  file_size_bytes: number | null;
  report_metadata: Record<string, unknown>;
  error_message: string | null;
  failure_reason: string | null;
  retry_count: number;
  generated_at: string | null;
  archived_at: string | null;
  approval_status: ReportApprovalStatus;
  approval_submitted_by: string | null;
  approval_submitted_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  approval_notes: string | null;
  rejection_reason: string | null;
  created_at: string;
}

export interface ReportListResponse {
  total: number;
  items: ReportSummary[];
}

export type CaseReviewStatus =
  | "not_submitted"
  | "pending_review"
  | "changes_requested"
  | "approved"
  | "rejected"
  | "closed";
export type ChecklistStatus = "passed" | "warning" | "failed" | "not_applicable";
export type CompletenessLabel =
  | "incomplete"
  | "partial"
  | "adequate"
  | "strong"
  | "complete";

export interface CaseReviewChecklistItem {
  key: string;
  label: string;
  status: ChecklistStatus;
  detail: string;
}

export interface EvidenceCompletenessResponse {
  investigation_id: string;
  score: number;
  label: CompletenessLabel;
  contributors: Record<string, number>;
  explanation: string[];
  generated_at: string;
}

export interface CaseReviewResponse {
  id: string;
  investigation_id: string;
  review_status: CaseReviewStatus;
  submitted_by: string | null;
  submitted_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  decision: string | null;
  closed_by: string | null;
  closed_at: string | null;
  closure_reason: string | null;
  override_reason: string | null;
  checklist: CaseReviewChecklistItem[];
  evidence_completeness_score: number;
  evidence_completeness_label: CompletenessLabel;
  evidence_completeness_contributors: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export type CaseClosureStatus = "draft" | "in_review" | "approved" | "closed" | "reopened";
export type CaseClosureChecklistStatus =
  | "pending"
  | "completed"
  | "blocked"
  | "not_applicable";
export type CaseFinalRiskRating =
  | "low"
  | "moderate"
  | "elevated"
  | "high"
  | "critical"
  | "not_assessed";
export type CaseDeliverableType =
  | "executive_report"
  | "technical_report"
  | "evidence_appendix"
  | "remediation_plan"
  | "scope_summary"
  | "audit_summary"
  | "final_package";
export type CaseDeliverableStatus =
  | "draft"
  | "ready"
  | "approved"
  | "delivered"
  | "archived";
export type CasePackageReadinessStatus =
  | "ready"
  | "ready_with_warnings"
  | "missing_required_deliverables";

export interface CaseClosureChecklistItem {
  id: string;
  investigation_id: string;
  closure_id: string | null;
  key: string;
  label: string;
  description: string | null;
  status: CaseClosureChecklistStatus;
  required: boolean;
  completed_by: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CaseDeliverable {
  id: string;
  investigation_id: string;
  title: string;
  deliverable_type: CaseDeliverableType;
  status: CaseDeliverableStatus;
  report_id: string | null;
  export_format: ReportFormat | null;
  file_reference: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface CaseDeliverableListResponse {
  total: number;
  items: CaseDeliverable[];
}

export interface EvidencePackageSummary {
  evidence_count: number;
  findings_with_evidence: number;
  findings_without_evidence: number;
  high_risk_evidence_highlights: string[];
  source_summary: Record<string, number>;
  evidence_chain_status: string;
  scope_relation: string;
  report_appendix_readiness: string;
}

export interface CasePackageManifestResponse {
  package_id: string;
  investigation_id: string;
  engagement_id: string | null;
  included_deliverables: CaseDeliverable[];
  missing_deliverables: CaseDeliverableType[];
  warnings: string[];
  readiness_status: CasePackageReadinessStatus;
  evidence_package: EvidencePackageSummary;
  generated_at: string;
  generated_by: string | null;
}

export interface CaseClosureResponse {
  id: string;
  investigation_id: string;
  status: CaseClosureStatus;
  closure_summary: string | null;
  final_risk_rating: CaseFinalRiskRating;
  reviewed_by: string | null;
  approved_by: string | null;
  closed_by: string | null;
  reviewed_at: string | null;
  approved_at: string | null;
  closed_at: string | null;
  checklist: CaseClosureChecklistItem[];
  deliverables: CaseDeliverable[];
  evidence_package: EvidencePackageSummary;
  warnings: string[];
  blockers: string[];
  created_at: string;
  updated_at: string;
}

export interface ReportApprovalResponse {
  report_id: string;
  investigation_id: string;
  approval_status: ReportApprovalStatus;
  approval_submitted_by: string | null;
  approval_submitted_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  approval_notes: string | null;
  rejection_reason: string | null;
}

export interface RemediationValidationResponse {
  finding_id: string;
  investigation_id: string;
  validation_status: RemediationValidationStatus;
  validation_owner: string | null;
  validation_notes: string | null;
  validated_by: string | null;
  validated_at: string | null;
  failure_reason: string | null;
}

export interface ReviewBoardItem {
  item_type:
    | "case_review"
    | "report_approval"
    | "remediation_validation"
    | "changes_requested"
    | "closure_ready";
  id: string;
  investigation_id: string;
  investigation_title: string;
  title: string;
  status: string;
  priority: string;
  risk: string;
  due_date: string | null;
  assigned_reviewer: string | null;
  created_at: string | null;
  detail: string;
}

export interface ReviewBoardResponse {
  generated_at: string;
  total: number;
  pending_case_reviews: number;
  pending_report_approvals: number;
  pending_remediation_validations: number;
  changes_requested: number;
  ready_for_closure: number;
  items: ReviewBoardItem[];
}

export interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  report_type: ReportType;
  sections: ReportSection[];
  is_default: boolean;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReportTemplateListResponse {
  total: number;
  items: ReportTemplate[];
}

export interface ReportTemplateCreateRequest {
  name: string;
  description: string;
  report_type: ReportType;
  sections: ReportSection[];
  is_default: boolean;
  is_active: boolean;
}

export interface ReportTemplateUpdateRequest {
  name?: string;
  description?: string;
  report_type?: ReportType;
  sections?: ReportSection[];
  is_default?: boolean;
  is_active?: boolean;
}

export interface ReportQualityWarning {
  code: string;
  message: string;
}

export interface ReportQualityResponse {
  investigation_id: string;
  report_id: string | null;
  template_id: string | null;
  warnings: ReportQualityWarning[];
  warning_count: number;
  ready_with_warnings: boolean;
  available_evidence: Record<string, number>;
  missing_sections: string[];
}

export interface ReportingCenterItem extends ReportSummary {
  investigation_title: string;
  generated_by_name: string | null;
  template_name: string | null;
}

export interface ReportingCenterResponse {
  total: number;
  limit: number;
  offset: number;
  items: ReportingCenterItem[];
}

export interface ReportingCenterFilters {
  report_type?: ReportType;
  status?: ReportStatus;
  format?: ReportFormat;
  investigation_id?: string;
  generated_by?: string;
  archived?: boolean;
  start_date?: string;
  end_date?: string;
  sort?: ReportSort;
  limit?: number;
  offset?: number;
}

export interface ReportBulkGenerateRequest {
  investigation_ids: string[];
  report_type: ReportType;
  template_id?: string | null;
  output_format: ReportFormat;
}

export interface ReportBulkGenerateResponse {
  generated: number;
  skipped: number;
  failed: number;
  results: Array<{
    investigation_id: string;
    report_id: string | null;
    status: "generated" | "skipped" | "failed";
    detail: string;
  }>;
}

export interface ReportActionResponse {
  report: ReportSummary;
  message: string;
}

export interface KnowledgeSearchResponse {
  query: string;
  mode: string;
  total: number;
  items: KnowledgeSearchResult[];
}

export interface KnowledgeSearchResult {
  document_id: string;
  title: string;
  source_type: string;
  file_path: string;
  chunk: string;
  score: number;
  tags: string[];
  category: string;
  framework: string | null;
  severity_relevance: "informational" | "low" | "medium" | "high";
  defensive_explanation: string;
  references: string[];
  related_findings: string[];
  mitre_relevance: string | null;
  sigma_relevance: string | null;
  remediation_guidance: string[];
  why_this_matters: string;
}

export interface DetectionKnowledgeCard {
  id: string;
  kind: "sigma" | "yara";
  title: string;
  description: string;
  category: string;
  framework: string;
  log_source: string | null;
  tags: string[];
  detection_idea: string;
  why_this_matters: string;
  remediation_guidance: string[];
  references: string[];
}

export interface DetectionKnowledgeResponse {
  total: number;
  items: DetectionKnowledgeCard[];
}

export interface FrameworkKnowledgeResponse {
  total: number;
  items: Array<{
    framework: string;
    description: string;
    defensive_use: string;
    common_categories: string[];
    references: string[];
  }>;
}

export interface AnalysisResponse {
  mode: string;
  status: string;
  provider: string;
  model: string | null;
  investigation_id: string;
  target_type?: string | null;
  target_value?: string | null;
  retrieval_mode?: string;
  executive_summary: CitedText;
  technical_summary: CitedText;
  observed_indicators: CitedText[];
  suspicious_findings: CitedText[];
  attack_hypotheses: CitedText[];
  severity: Severity;
  confidence: number;
  recommended_next_steps: AnalysisRecommendation[];
  framework_mappings: AnalysisFrameworkMapping[];
  citations: AnalysisCitation[];
  errors: string[];
  provider_diagnostics?: AnalysisProviderDiagnostics;
}

export interface AnalysisProviderDiagnostics {
  provider_configured: boolean;
  model: string | null;
  feature_enabled: boolean;
  last_error_category: string | null;
}

export interface CitedText {
  text: string;
  citation_ids: string[];
}

export interface AnalysisRecommendation {
  action: string;
  rationale: string;
  citation_ids: string[];
}

export interface AnalysisFrameworkMapping {
  framework: string;
  control: string;
  rationale: string;
  citation_ids: string[];
}

export interface AnalysisCitation {
  id: string;
  source_type: string;
  title: string;
  summary: string;
  metadata: Record<string, unknown>;
}

export interface CountItem {
  label: string;
  count: number;
}

export interface LatestActivityItem {
  id: string;
  timestamp: string;
  source: string;
  title: string;
  summary: string;
  severity: Severity;
}

export interface InvestigationAnalyticsItem {
  id: string;
  title: string;
  status: InvestigationStatus;
  created_at: string;
  updated_at: string;
}

export interface ReportAnalyticsItem {
  id: string;
  investigation_id: string;
  title: string | null;
  report_type: string;
  status: string;
  created_at: string;
}

export interface FindingAnalyticsItem {
  id: string;
  investigation_id: string;
  title: string;
  severity: Severity;
  status: FindingStatus;
  source: string;
  risk_score: number;
  confidence_score: number;
  created_at: string;
}

export interface RiskSummary {
  risk_score: number;
  risk_level: "Low" | "Medium" | "High" | "Critical";
  highest_severity: Severity | null;
  highest_severity_finding: FindingAnalyticsItem | null;
  high_or_critical_findings: number;
  average_finding_confidence: number;
}

export interface FindingsAnalyticsSummary {
  total: number;
  by_severity: Record<Severity, number>;
  by_status: Record<FindingStatus, number>;
  average_confidence: number;
  highest_severity_finding: FindingAnalyticsItem | null;
}

export interface ReconAnalyticsSummary {
  total_entities: number;
  entity_counts: Record<string, number>;
  relationship_count: number;
  top_external_dependencies: CountItem[];
  top_technologies: CountItem[];
}

export interface TargetAnalyticsSummary {
  total: number;
  by_type: Record<string, number>;
}

export interface CorrelationAnalyticsSummary {
  total_nodes: number;
  total_edges: number;
  by_confidence: Record<string, number>;
}

export interface ReportAnalyticsSummary {
  total: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  ready: number;
  latest_reports: ReportAnalyticsItem[];
}

export interface AiAnalysisAnalyticsSummary {
  total: number;
  available: boolean;
  latest_at: string | null;
  by_risk: Record<string, number>;
}

export interface TimelineAnalyticsSummary {
  total: number;
  by_event_type: Record<string, number>;
  by_source: Record<string, number>;
}

export interface InvestigationAnalyticsResponse {
  investigation_id: string;
  generated_at: string;
  risk_summary: RiskSummary;
  findings_summary: FindingsAnalyticsSummary;
  recon_summary: ReconAnalyticsSummary;
  target_summary: TargetAnalyticsSummary;
  correlation_summary: CorrelationAnalyticsSummary;
  report_summary: ReportAnalyticsSummary;
  ai_analysis_summary: AiAnalysisAnalyticsSummary;
  timeline_summary: TimelineAnalyticsSummary;
  top_assets: CountItem[];
  top_technologies: CountItem[];
  latest_activity: LatestActivityItem[];
}

export interface InvestigationDashboardSummary {
  total: number;
  active: number;
  closed: number;
  by_status: Record<InvestigationStatus, number>;
}

export interface OpenHighRiskItem {
  finding_id: string;
  investigation_id: string;
  investigation_title: string;
  title: string;
  severity: Severity;
  risk_score: number;
  created_at: string;
}

export interface DashboardAnalyticsResponse {
  generated_at: string;
  investigation_summary: InvestigationDashboardSummary;
  target_summary: TargetAnalyticsSummary;
  recon_summary: ReconAnalyticsSummary;
  findings_summary: FindingsAnalyticsSummary;
  report_summary: ReportAnalyticsSummary;
  ai_analysis_summary: AiAnalysisAnalyticsSummary;
  timeline_summary: TimelineAnalyticsSummary;
  latest_investigations: InvestigationAnalyticsItem[];
  latest_reports: ReportAnalyticsItem[];
  recent_activity: LatestActivityItem[];
  open_high_risk_items: OpenHighRiskItem[];
}

export interface DashboardMetricsResponse {
  generated_at: string;
  investigation_metrics: {
    findings_count: number;
    validated_findings: number;
    open_tasks: number;
    overdue_tasks: number;
    average_confidence: number;
    health_score: number;
    urgent_investigations: number;
    overdue_investigations: number;
  };
  analyst_metrics: {
    assigned_investigations: number;
    assigned_findings: number;
    pending_reviews: number;
    completed_remediations: number;
  };
  risk_metrics: {
    severity_distribution: Record<Severity, number>;
    confidence_average: number;
    unresolved_findings: number;
  };
}

export type NoteType =
  | "analyst_note"
  | "triage_note"
  | "remediation_note"
  | "escalation_note"
  | "validation_note"
  | "closure_note"
  | "evidence_note"
  | "executive_note"
  | "timeline_note";

export interface InvestigationNote {
  id: string;
  investigation_id: string;
  created_by: string | null;
  updated_by: string | null;
  author_id: string | null;
  title: string;
  content: string;
  note: string;
  note_type: NoteType;
  pinned: boolean;
  archived: boolean;
  visibility: "investigation" | "owners";
  references: string[];
  created_at: string;
  updated_at: string;
}

export interface InvestigationNoteListResponse {
  total: number;
  items: InvestigationNote[];
}

export interface InvestigationNoteCreateRequest {
  title: string;
  content: string;
  note_type: NoteType;
  pinned?: boolean;
  visibility?: "investigation" | "owners";
  references?: string[];
}

export interface InvestigationNoteUpdateRequest {
  title?: string;
  content?: string;
  note_type?: NoteType;
  pinned?: boolean;
  archived?: boolean;
  visibility?: "investigation" | "owners";
  references?: string[];
}

export interface EvidenceBookmark {
  id: string;
  investigation_id: string;
  entity_id: string | null;
  finding_id: string | null;
  report_id: string | null;
  bookmark_type: "entity" | "finding" | "report";
  title: string;
  note: string | null;
  created_by: string | null;
  created_at: string;
}

export interface EvidenceBookmarkListResponse {
  total: number;
  items: EvidenceBookmark[];
}

export interface EvidenceBookmarkCreateRequest {
  entity_id?: string | null;
  finding_id?: string | null;
  report_id?: string | null;
  title: string;
  note?: string | null;
}

export interface InvestigationTag {
  id: string;
  name: string;
  color: string;
  created_at: string;
}

export interface InvestigationTagListResponse {
  total: number;
  items: InvestigationTag[];
}

export interface InvestigationPriorityUpdateRequest {
  priority: InvestigationPriority;
  business_impact?: string | null;
  due_date?: string | null;
}

export interface InvestigationPriorityResponse {
  investigation_id: string;
  priority: InvestigationPriority;
  business_impact: string | null;
  owner_id: string;
  due_date: string | null;
  overdue: boolean;
}

export interface InvestigationSummaryResponse {
  investigation_id: string;
  scope: string;
  observed_defensive_concerns: string[];
  highest_priority_findings: Array<{
    id: string;
    title: string;
    severity: string;
    status: string;
    risk_score: number;
  }>;
  remediation_progress: {
    total_findings: number;
    remediated: number;
    accepted_risk: number;
    unresolved: number;
    completion_percent: number;
  };
  next_recommended_analyst_actions: string[];
  evidence_references: string[];
}

export type TaskStatus =
  | "todo"
  | "in_progress"
  | "blocked"
  | "validation"
  | "completed";
export type TaskPriority = "critical" | "urgent" | "high" | "medium" | "low";

export interface InvestigationTask {
  id: string;
  investigation_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assigned_to: string | null;
  due_date: string | null;
  remediation_link: string | null;
  blockers: string | null;
  finding_id: string | null;
  playbook_run_id: string | null;
  evidence_reference_ids: string[];
  created_by: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  archived_at: string | null;
}

export interface InvestigationTaskListResponse {
  total: number;
  items: InvestigationTask[];
}

export interface InvestigationTaskCreateRequest {
  investigation_id?: string | null;
  title: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  assigned_to?: string | null;
  due_date?: string | null;
  remediation_link?: string | null;
  blockers?: string | null;
  finding_id?: string | null;
  playbook_run_id?: string | null;
  evidence_reference_ids?: string[];
}

export interface InvestigationTaskUpdateRequest {
  title?: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  assigned_to?: string | null;
  due_date?: string | null;
  remediation_link?: string | null;
  blockers?: string | null;
  finding_id?: string | null;
  playbook_run_id?: string | null;
  evidence_reference_ids?: string[];
  archived?: boolean;
}

export type EvidenceType =
  | "recon"
  | "dns"
  | "infrastructure"
  | "screenshot"
  | "report"
  | "correlation"
  | "finding"
  | "threat_intel"
  | "analyst_note";

export interface InvestigationEvidence {
  id: string;
  investigation_id: string;
  finding_id: string | null;
  note_id: string | null;
  task_id: string | null;
  title: string;
  description: string | null;
  evidence_type: EvidenceType;
  source: string;
  confidence: number;
  tags: string[];
  analyst_comment: string | null;
  review_status: "collected" | "reviewed" | "validated" | "dismissed";
  reviewed_by: string | null;
  reviewed_at: string | null;
  analyst_note: string | null;
  confidence_score: number;
  archived_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvestigationEvidenceListResponse {
  total: number;
  items: InvestigationEvidence[];
}

export type MonitoringStatus = "healthy" | "degraded" | "unavailable";
export type MonitoringSeverity = "info" | "warning" | "critical";

export interface MonitoringServiceStatus {
  key: string;
  label: string;
  status: MonitoringStatus;
  detail: string;
  metadata: Record<string, string | number | boolean | null>;
}

export interface MonitoringSystem {
  generated_at: string;
  source: "container" | "local_agent";
  metric_scope: string;
  available: boolean;
  stale: boolean;
  agent_id: string | null;
  platform: string;
  collected_at: string | null;
  received_at: string | null;
  cpu_percent: number | null;
  memory_percent: number | null;
  disk_percent: number | null;
  process_count: number | null;
  uptime_seconds: number | null;
  detail: string;
}

export interface MonitoringAssetItem {
  investigation_id: string;
  title: string;
  status: MonitoringStatus;
  investigation_status: string;
  scope_status: string;
  authorization_status: string;
  targets: number;
  stale_targets: number;
  unresolved_high: number;
  unresolved_critical: number;
  evidence_records: number;
  report_status: string;
  closure_status: string;
  action_url: string;
}

export interface MonitoringAlert {
  id: string | null;
  key: string;
  severity: MonitoringSeverity;
  title: string;
  message: string;
  category: string;
  source: string;
  observed_at: string;
  action_url: string;
  investigation_id: string | null;
  count: number;
  suppressed: boolean;
  suppressed_due_to_maintenance: boolean;
  suppression_reason: string | null;
}

export interface MonitoringPolicy {
  id: string; rule_key: string; title: string; description: string; enabled: boolean;
  severity_override: MonitoringSeverity | null; threshold_value: number | null;
  threshold_unit: string | null; cooldown_minutes: number; dedupe_key: string;
  max_alerts_per_rule: number; acknowledge_behavior: "keep_active" | "suppress";
  created_by: string | null; updated_by: string | null; created_at: string; updated_at: string;
}
export interface MonitoringPolicyListResponse { total: number; items: MonitoringPolicy[]; }
export interface MaintenanceWindow {
  id: string; title: string; start_time: string; end_time: string; affected_assets: string[];
  affected_services: string[]; suppress_alerts: boolean; reason: string;
  created_by: string | null; updated_by: string | null; created_at: string; updated_at: string;
  status: "scheduled" | "active" | "completed";
}
export interface MaintenanceWindowListResponse { total: number; items: MaintenanceWindow[]; }
export interface AlertSuppressionResponse { id: string; alert_id: string; source: "manual" | "maintenance"; reason: string; starts_at: string; ends_at: string | null; active: boolean; suppressed_due_to_maintenance: boolean; }

export type MonitoringTriageStatus = "new" | "triaged" | "investigating" | "muted" | "resolved" | "false_positive";
export interface MonitoringTriageItem {
  alert_id: string;
  status: MonitoringTriageStatus;
  owner_id: string | null;
  owner_name: string | null;
  severity: NotificationSeverity;
  source: string;
  related_asset_id: string | null;
  related_finding_id: string | null;
  title: string;
  description: string;
  action_url: string | null;
  first_seen: string;
  last_seen: string;
  notes: string | null;
  resolution_summary: string | null;
  suppressed: boolean;
  suppressed_due_to_maintenance: boolean;
}
export interface MonitoringTriageListResponse { total: number; limit: number; offset: number; items: MonitoringTriageItem[]; }

export interface MonitoringRecentError {
  category: string;
  action: string;
  occurred_at: string;
  investigation_id: string | null;
}

export interface MonitoringOverviewResponse {
  generated_at: string;
  status: MonitoringStatus;
  release_version: string;
  polling_interval_options: number[];
  recommended_polling_interval: number;
  services: {
    generated_at: string;
    status: MonitoringStatus;
    items: MonitoringServiceStatus[];
  };
  system: MonitoringSystem;
  assets: {
    generated_at: string;
    stale_after_days: number;
    investigations: number;
    targets: number;
    healthy_assets: number;
    assets_needing_review: number;
    stale_assets: number;
    high_risk_assets: number;
    out_of_scope_assets: number;
    unresolved_high: number;
    unresolved_critical: number;
    findings_by_severity: Record<string, number>;
    authorization_risks: number;
    repeated_report_failures: number;
    repeated_ai_degraded: number;
    items: MonitoringAssetItem[];
  };
  alerts: {
    generated_at: string;
    total: number;
    notifications_created: number;
    notifications_existing: number;
    items: MonitoringAlert[];
  };
  recent_errors: MonitoringRecentError[];
}

export interface LanRiskIndicator {
  key: string;
  severity: "info" | "warning" | "critical";
  label: string;
  detail: string;
}

export interface LanAsset {
  id: string;
  ip_address: string;
  mac_address: string | null;
  hostname: string | null;
  vendor: string | null;
  asset_type: string;
  status: "online" | "offline" | "unknown";
  source: string;
  first_seen: string;
  last_seen: string | null;
  last_checked_at: string | null;
  confidence: number;
  notes: string | null;
  is_authorized: boolean;
  monitoring_enabled: boolean;
  enrolled_at: string | null;
  capabilities: string[];
  criticality: "low" | "medium" | "high" | "critical";
  owner: string | null;
  business_function: string | null;
  environment: string | null;
  agent_connected: boolean;
  response_latency_ms: number | null;
  risk_indicators: LanRiskIndicator[];
  created_at: string;
  updated_at: string;
}

export interface EnrollmentToken {
  id: string; name: string; description: string | null; token_hint: string;
  allowed_cidr: string | null; max_enrollments: number | null; enrollment_count: number;
  expires_at: string; created_by: string | null; created_at: string; revoked_at: string | null;
  status: "active" | "expired" | "revoked" | "exhausted"; token?: string;
}
export interface AgentInventoryItem extends LanAsset {
  os_name: string | null; os_version: string | null; agent_version: string | null;
  telemetry_fresh: boolean; enrollment_token_label: string | null;
  group_ids: string[]; group_names: string[];
}
export interface GroupCoverage { group_id: string; group_name: string; total_assets: number; monitored_by_agent: number; stale_agents: number; risk_indicators: number; }
export interface AgentInventoryResponse {
  total: number;
  coverage: { total_lan_assets: number; monitored_by_agent: number; missing_agent: number; stale_agents: number; unauthorized_assets: number; critical_assets_without_telemetry: number; groups: GroupCoverage[] };
  items: AgentInventoryItem[];
}
export interface AssetGroup { id: string; name: string; description: string | null; asset_ids: string[]; total_assets: number; monitored_by_agent: number; stale_agents: number; risk_indicators: number; created_by: string | null; created_at: string; updated_at: string; }
export interface ServiceBaselineIndicator { asset_id: string; port: number; indicator_type: "missing_expected_service" | "unexpected_open_service"; severity: "warning" | "critical"; detail: string; }
export interface ServiceBaseline { id: string; name: string; description: string | null; asset_id: string | null; group_id: string | null; expected_ports: number[]; allowed_ports: number[]; indicators: ServiceBaselineIndicator[]; created_by: string | null; created_at: string; updated_at: string; }

export interface LanAssetListResponse {
  generated_at: string;
  enabled: boolean;
  allowed_cidrs: string[];
  discovery_interval_seconds: number;
  ping_enabled: boolean;
  service_check_enabled: boolean;
  docker_limited: boolean;
  limitation: string;
  total: number;
  online: number;
  offline: number;
  unauthorized: number;
  agent_connected: number;
  items: LanAsset[];
}

export interface LanTelemetryItem {
  id: string;
  lan_asset_id: string;
  cpu_percent: number | null;
  memory_percent: number | null;
  disk_percent: number | null;
  uptime_seconds: number | null;
  os_name: string | null;
  os_version: string | null;
  agent_version: string | null;
  collected_at: string;
  metadata: Record<string, unknown>;
}

export interface LanTelemetryListResponse {
  total: number;
  items: LanTelemetryItem[];
}

export interface LanServiceObservation {
  id: string;
  lan_asset_id: string;
  ip_address: string;
  port: number;
  protocol: string;
  service_name: string | null;
  service_label: string | null;
  confidence: number;
  banner_hint: string | null;
  non_standard_ssh: boolean;
  status: string;
  observed_at: string;
  source: string;
}

export interface LanServiceCheckResponse {
  asset_id: string;
  ip_address: string;
  ports_checked: number;
  observations_created: number;
  open_ports: number;
  message: string;
}

export interface LanServiceListResponse {
  total: number;
  service_checks_enabled: boolean;
  items: LanServiceObservation[];
}

export type MonitoringChangeSeverity = "info" | "low" | "medium" | "high" | "critical";

export interface MonitoringChange {
  id: string;
  asset_id: string | null;
  event_type: string;
  severity: MonitoringChangeSeverity;
  title: string;
  description: string;
  old_value: string | null;
  new_value: string | null;
  source: string;
  detected_at: string;
  acknowledged_at: string | null;
  metadata: Record<string, unknown>;
}

export interface MonitoringChangeListResponse {
  total: number;
  limit: number;
  offset: number;
  items: MonitoringChange[];
}

export interface MonitoringChangeOverview {
  total: number;
  unacknowledged: number;
  critical: number;
  high: number;
  new_assets: number;
  port_changes: number;
  agent_changes: number;
  baseline_changes: number;
}

export interface ServiceHistoryItem {
  id: string;
  asset_id: string;
  port: number;
  protocol: string;
  previous_status: string | null;
  current_status: string;
  service_name: string | null;
  confidence: number;
  observed_at: string;
  source: string;
}

export interface ServiceHistoryListResponse {
  total: number;
  limit: number;
  offset: number;
  items: ServiceHistoryItem[];
}

export interface AssetMonitoringHistory {
  asset_id: string;
  changes: MonitoringChangeListResponse;
  telemetry_samples: number;
  telemetry_first_at: string | null;
  telemetry_last_at: string | null;
  latest_cpu_percent: number | null;
  latest_memory_percent: number | null;
  latest_disk_percent: number | null;
}

export interface LanDiscoveryResponse {
  enabled: boolean;
  cidr: string;
  observations_received: number;
  assets_created: number;
  assets_updated: number;
  service_observations_created: number;
  limitation: string | null;
  message: string;
}

export type VulnerabilityBaselineStatus = "open" | "acknowledged" | "in_progress" | "resolved" | "false_positive";

export interface VulnerabilityBaselineFinding {
  id: string;
  lan_asset_id: string | null;
  investigation_id: string | null;
  rule_key: string;
  title: string;
  description: string;
  severity: Severity;
  confidence: "low" | "medium" | "high";
  status: VulnerabilityBaselineStatus;
  source: string;
  evidence_summary: string;
  recommendation: string;
  remediation_owner: string | null;
  remediation_due_date: string | null;
  first_seen: string;
  last_seen: string;
  resolved_at: string | null;
  metadata: Record<string, unknown>;
  asset_ip: string | null;
  asset_hostname: string | null;
  asset_criticality: string | null;
  overdue: boolean;
  missing_owner: boolean;
}

export interface VulnerabilityBaselineListResponse {
  generated_at: string;
  total: number;
  items: VulnerabilityBaselineFinding[];
}

export interface VulnerabilityBaselineOverview {
  generated_at: string;
  enabled: boolean;
  total: number;
  open: number;
  acknowledged: number;
  in_progress: number;
  resolved: number;
  false_positive: number;
  by_severity: Record<Severity, number>;
  affected_assets: number;
  stale_agents: number;
  risky_services: number;
  overdue_remediation: number;
  missing_remediation_owner: number;
}

export interface VulnerabilityBaselineRunResponse {
  generated_at: string;
  evaluated_assets: number;
  evaluated_investigations: number;
  detected: number;
  created: number;
  refreshed: number;
  auto_resolved: number;
  notifications_created: number;
  message: string;
}
