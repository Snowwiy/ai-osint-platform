export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type InvestigationStatus =
  | "draft"
  | "active"
  | "triage"
  | "monitoring"
  | "remediation"
  | "validated"
  | "archived";
export type InvestigationPriority = "low" | "medium" | "high" | "urgent";

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
  owner_id: string;
  reviewer_id: string | null;
  authorization_statement: string;
  scope_definition: string | null;
  priority: InvestigationPriority;
  business_impact: string | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvestigationListResponse {
  total: number;
  items: Investigation[];
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
}

export interface MemberAddRequest {
  user_id?: string | null;
  email?: string | null;
  username?: string | null;
  role: InvestigationMemberRole;
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
}

export interface InvestigationUpdateRequest {
  title?: string;
  description?: string | null;
  status?: InvestigationStatus;
  scope_definition?: string | null;
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

export type ReportType = "executive" | "technical";
export type ReportFormat = "html" | "md" | "pdf" | "docx";
export type ReportStatus = "pending" | "generating" | "ready" | "failed";

export interface ReportCreateRequest {
  report_type: ReportType;
  title?: string | null;
}

export interface ReportSummary {
  id: string;
  investigation_id: string;
  generated_by: string | null;
  title: string | null;
  report_type: ReportType;
  report_format: string;
  status: ReportStatus;
  file_size_bytes: number | null;
  report_metadata: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
}

export interface ReportListResponse {
  total: number;
  items: ReportSummary[];
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
  | "evidence_note"
  | "remediation_note"
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
}

export interface InvestigationNoteUpdateRequest {
  title?: string;
  content?: string;
  note_type?: NoteType;
  pinned?: boolean;
  archived?: boolean;
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
  | "open"
  | "in_progress"
  | "blocked"
  | "completed"
  | "cancelled";
export type TaskPriority = "critical" | "high" | "medium" | "low";

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
  finding_id: string | null;
  evidence_reference_ids: string[];
  created_by: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
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
  finding_id?: string | null;
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
  finding_id?: string | null;
  evidence_reference_ids?: string[];
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
