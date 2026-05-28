export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type InvestigationStatus = "draft" | "active" | "completed" | "archived";

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: "admin" | "analyst" | string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
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
  authorization_statement: string;
  scope_definition: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvestigationListResponse {
  total: number;
  items: Investigation[];
}

export interface InvestigationCreateRequest {
  title: string;
  description?: string | null;
  authorization_statement: string;
  scope_definition?: string | null;
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
  created_at: string;
  updated_at: string;
  evidence: FindingEvidence[];
  tags: string[];
}

export type FindingStatus = "open" | "validated" | "false_positive" | "resolved";

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
