import type {
  AdminQaStatusResponse,
  AdminUserActionResponse,
  AdminUserFilters,
  AdminUserListResponse,
  AdminOverviewResponse,
  AdminSettingsResponse,
  AdminSettingsUpdate,
  AnalysisResponse,
  AuthorizationEvidence,
  AuthorizationEvidenceCreateRequest,
  AuthorizationEvidenceUpdateRequest,
  AuditLogFilters,
  AuditLogListResponse,
  CaseReviewResponse,
  CaseClosureChecklistItem,
  CaseClosureChecklistStatus,
  CaseClosureResponse,
  CaseDeliverable,
  CaseDeliverableListResponse,
  CaseDeliverableStatus,
  CaseDeliverableType,
  CaseFinalRiskRating,
  CasePackageManifestResponse,
  CorrelationResponse,
  DataQualityIssue,
  DataQualityIssueFilters,
  DataQualityIssueListResponse,
  DataQualityOverviewResponse,
  DataQualityScanResponse,
  CrossInvestigationCorrelationResponse,
  CrossInvestigationSignalType,
  CollaborationDashboardResponse,
  DashboardAnalyticsResponse,
  DashboardMetricsResponse,
  DashboardOverviewResponse,
  DashboardHighlightsResponse,
  DashboardTimelineResponse,
  DashboardTriageResponse,
  DetectionKnowledgeResponse,
  DefensivePlaybook,
  DemoSeedResponse,
  Engagement,
  EngagementCreateRequest,
  EngagementListResponse,
  EngagementScopeItem,
  EngagementScopeItemCreateRequest,
  EngagementScopeItemUpdateRequest,
  EngagementUpdateRequest,
  ExecutiveDashboardResponse,
  ExecutiveInvestigationSummaryResponse,
  ExecutivePostureResponse,
  ExecutiveRecommendationsResponse,
  ExecutiveTrendsResponse,
  EnvironmentValidationResponse,
  EvidenceBookmark,
  EvidenceBookmarkCreateRequest,
  EvidenceBookmarkListResponse,
  EvidenceCompletenessResponse,
  EvidenceIntelligenceEvidenceResponse,
  EvidenceIntelligenceIOCResponse,
  EvidenceIntelligenceOverviewResponse,
  EvidenceIntelligencePriorityResponse,
  EvidenceIntelligenceTimelineResponse,
  Finding,
  FindingPlaybookRecommendation,
  FindingRemediationResponse,
  FindingRemediationUpdate,
  FindingStatus,
  FeatureAvailabilityResponse,
  FeatureFlagSettings,
  HealthResponse,
  InvestigationEvidenceListResponse,
  InvestigationAnalyticsResponse,
  Investigation,
  InvestigationReadinessResponse,
  InvestigationCoverageResponse,
  InvestigationRecommendationsResponse,
  InvestigationRiskScoreResponse,
  InvestigationStage,
  LanAsset,
  LanAssetListResponse,
  LanDiscoveryResponse,
  VulnerabilityBaselineFinding,
  VulnerabilityBaselineListResponse,
  VulnerabilityBaselineOverview,
  VulnerabilityBaselineRunResponse,
  VulnerabilityBaselineStatus,
  LanServiceListResponse,
  LanServiceCheckResponse,
  MonitoringActivationStatus,
  TargetServiceCheckStatus,
  AssetMonitoringHistory,
  MonitoringChangeListResponse,
  MonitoringChangeOverview,
  MonitoringChangeSeverity,
  ServiceHistoryListResponse,
  LanTelemetryListResponse,
  InvestigationEscalation,
  InvestigationHandoff,
  InvestigationHandoffRequest,
  InvestigationPrioritizationResponse,
  InvestigationOwnership,
  InvestigationOwnershipUpdate,
  InvestigationCreateRequest,
  InvestigationGraphResponse,
  InvestigationListResponse,
  InvestigationPurgeImpact,
  InvestigationBulkRequest,
  InvestigationBulkResponse,
  InvestigationQueueFilters,
  InvestigationQueueResponse,
  InvestigationMember,
  InvestigationPriorityResponse,
  InvestigationPriorityUpdateRequest,
  InvestigationSummaryResponse,
  InvestigationTag,
  InvestigationTagListResponse,
  MemberAddRequest,
  MemberUpdateRequest,
  InvestigationNoteCreateRequest,
  InvestigationNoteListResponse,
  InvestigationNoteUpdateRequest,
  InvestigationTaskCreateRequest,
  InvestigationTaskListResponse,
  InvestigationTaskUpdateRequest,
  InvestigationUpdateRequest,
  KnowledgeSearchResponse,
  MaintenanceDryRunResponse,
  IOCConfidence,
  IOCCorrelationResponse,
  IOCDetail,
  IOCGuidanceResponse,
  IOCListResponse,
  IOCType,
  FrameworkKnowledgeResponse,
  GlobalSearchFilters,
  GlobalSearchResponse,
  NotificationActionResponse,
  NotificationFilters,
  NotificationListResponse,
  NotificationMarkAllReadResponse,
  NotificationUnreadCountResponse,
  MonitoringOverviewResponse,
  MonitoringTriageItem,
  MonitoringTriageListResponse,
  MonitoringTriageStatus,
  MonitoringPolicy,
  MonitoringPolicyListResponse,
  MaintenanceWindow,
  MaintenanceWindowListResponse,
  AlertSuppressionResponse,
  AgentInventoryItem,
  AgentInventoryResponse,
  AssetGroup,
  EnrollmentToken,
  ServiceBaseline,
  EndpointPostureOverview,
  EndpointRecommendation,
  EndpointRecommendationListResponse,
  EndpointRecommendationStatus,
  EndpointSecurityPosture,
  OperationsStatusResponse,
  PlaybookRun,
  PlaybookRunStatus,
  PlaybookRunStepStatus,
  ReportActionResponse,
  ReportApprovalResponse,
  ReportBulkGenerateRequest,
  ReportBulkGenerateResponse,
  ReportCreateRequest,
  ReportFormat,
  ReportListResponse,
  ReportQualityResponse,
  ReportSummary,
  ReportTemplate,
  ReportTemplateCreateRequest,
  ReportTemplateListResponse,
  ReportTemplateUpdateRequest,
  ReportingCenterFilters,
  ReportingCenterResponse,
  RegisterRequest,
  RegisterResponse,
  RegistrationPolicyResponse,
  RetentionSettings,
  RetentionStatusResponse,
  ReconResponse,
  RestoreValidationRequest,
  RestoreValidationResponse,
  RemediationValidationResponse,
  ReviewBoardResponse,
  ScopeCheckRequest,
  ScopeCheckResponse,
  SavedView,
  SavedViewCreateRequest,
  SavedViewListResponse,
  SavedViewType,
  SavedViewUpdateRequest,
  StaleNotificationArchiveResponse,
  Target,
  TargetCreateRequest,
  TargetListResponse,
  TargetType,
  ThreatCampaignListResponse,
  ThreatGroupListResponse,
  ThreatIndicatorListResponse,
  ThreatInfrastructureResponse,
  ThreatOverviewResponse,
  ThreatTechniqueListResponse,
  ThreatTimelineResponse,
  TimelineResponse,
  TokenResponse,
  UserProfile,
  AnalystWorkloadResponse,
  PlatformUserRole,
} from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const API_ROOT_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, "");

const ACCESS_TOKEN_KEY = "raventech.accessToken";
const REFRESH_TOKEN_KEY = "raventech.refreshToken";
const DEFAULT_TIMEOUT_MS = 30_000;
export const AUTH_EXPIRED_EVENT = "raventech:auth-expired";

interface ApiErrorMetadata {
  category?: string;
  detail?: string;
  requestId?: string;
  suggestion?: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly endpoint?: string,
    public readonly metadata: ApiErrorMetadata = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface FileDownloadResult {
  blob: Blob | null;
  filename: string;
  mimeType: string;
  handledExternally: boolean;
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken?: string | null): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) {
    window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }
}

export function clearTokens(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export async function login(identifier: string, password: string): Promise<TokenResponse> {
  const body = identifier.includes("@")
    ? { email: identifier, password }
    : { username: identifier, password };
  let response: TokenResponse;
  try {
    response = await request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
      skipAuth: true,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      console.warn("Login rejected by backend.", {
        endpoint: error.endpoint,
        status: error.status,
      });
      throw new ApiError("Invalid username or password.", 401, error.endpoint);
    }
    throw error;
  }
  setTokens(response.access_token, response.refresh_token);
  return response;
}

export async function getRegistrationPolicy(): Promise<RegistrationPolicyResponse> {
  return request<RegistrationPolicyResponse>("/auth/registration-policy", {
    skipAuth: true,
  });
}

export async function registerAccount(
  body: RegisterRequest,
): Promise<RegisterResponse> {
  try {
    return await request<RegisterResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
      skipAuth: true,
    });
  } catch (error) {
    if (error instanceof ApiError && [403, 409, 422].includes(error.status)) {
      throw new ApiError(
        error.metadata.detail || error.message,
        error.status,
        error.endpoint,
        error.metadata,
      );
    }
    throw error;
  }
}

export async function logout(): Promise<void> {
  const refreshToken = window.localStorage.getItem(REFRESH_TOKEN_KEY);
  try {
    await request<void>("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } finally {
    clearTokens();
  }
}

export async function getMe(): Promise<UserProfile> {
  return request<UserProfile>("/auth/me");
}

export async function getBackendHealth(): Promise<HealthResponse> {
  return requestRoot<HealthResponse>("/health", { skipAuth: true });
}

export async function listInvestigations(): Promise<InvestigationListResponse> {
  return request<InvestigationListResponse>("/investigations/");
}

export async function listInvestigationsWithScope(
  scope: string,
): Promise<InvestigationListResponse> {
  const params = new URLSearchParams();
  if (scope !== "all") {
    params.set("scope", scope);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<InvestigationListResponse>(`/investigations/${suffix}`);
}

export async function listEngagements(
  includeArchived = false,
): Promise<EngagementListResponse> {
  const suffix = includeArchived ? "?include_archived=true" : "";
  return request<EngagementListResponse>(`/engagements/${suffix}`);
}

export async function createEngagement(
  body: EngagementCreateRequest,
): Promise<Engagement> {
  return request<Engagement>("/engagements/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getEngagement(id: string): Promise<Engagement> {
  return request<Engagement>(`/engagements/${id}`);
}

export async function updateEngagement(
  id: string,
  body: EngagementUpdateRequest,
): Promise<Engagement> {
  return request<Engagement>(`/engagements/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function archiveEngagement(id: string): Promise<Engagement> {
  return request<Engagement>(`/engagements/${id}/archive`, {
    method: "POST",
  });
}

export async function listEngagementScopeItems(
  engagementId: string,
): Promise<EngagementScopeItem[]> {
  return request<EngagementScopeItem[]>(`/engagements/${engagementId}/scope`);
}

export async function createEngagementScopeItem(
  engagementId: string,
  body: EngagementScopeItemCreateRequest,
): Promise<EngagementScopeItem> {
  return request<EngagementScopeItem>(`/engagements/${engagementId}/scope`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateEngagementScopeItem(
  engagementId: string,
  scopeItemId: string,
  body: EngagementScopeItemUpdateRequest,
): Promise<EngagementScopeItem> {
  return request<EngagementScopeItem>(
    `/engagements/${engagementId}/scope/${scopeItemId}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export async function deleteEngagementScopeItem(
  engagementId: string,
  scopeItemId: string,
): Promise<void> {
  return request<void>(`/engagements/${engagementId}/scope/${scopeItemId}`, {
    method: "DELETE",
  });
}

export async function listAuthorizationEvidence(
  engagementId: string,
): Promise<AuthorizationEvidence[]> {
  return request<AuthorizationEvidence[]>(
    `/engagements/${engagementId}/authorization`,
  );
}

export async function createAuthorizationEvidence(
  engagementId: string,
  body: AuthorizationEvidenceCreateRequest,
): Promise<AuthorizationEvidence> {
  return request<AuthorizationEvidence>(
    `/engagements/${engagementId}/authorization`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function updateAuthorizationEvidence(
  engagementId: string,
  evidenceId: string,
  body: AuthorizationEvidenceUpdateRequest,
): Promise<AuthorizationEvidence> {
  return request<AuthorizationEvidence>(
    `/engagements/${engagementId}/authorization/${evidenceId}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export async function deleteAuthorizationEvidence(
  engagementId: string,
  evidenceId: string,
): Promise<void> {
  return request<void>(
    `/engagements/${engagementId}/authorization/${evidenceId}`,
    {
      method: "DELETE",
    },
  );
}

export async function checkEngagementScope(
  engagementId: string,
  body: ScopeCheckRequest,
): Promise<ScopeCheckResponse> {
  return request<ScopeCheckResponse>(`/engagements/${engagementId}/scope/check`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function createInvestigation(
  body: InvestigationCreateRequest,
): Promise<Investigation> {
  return request<Investigation>("/investigations/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getInvestigation(id: string): Promise<Investigation> {
  return request<Investigation>(`/investigations/${id}`);
}

export async function getInvestigationReadiness(
  id: string,
): Promise<InvestigationReadinessResponse> {
  return request<InvestigationReadinessResponse>(
    `/investigations/${id}/readiness`,
  );
}

export async function getExecutiveInvestigationSummary(
  id: string,
): Promise<ExecutiveInvestigationSummaryResponse> {
  return request<ExecutiveInvestigationSummaryResponse>(
    `/investigations/${id}/executive-summary`,
  );
}

export async function getInvestigationRiskScore(
  id: string,
): Promise<InvestigationRiskScoreResponse> {
  return request<InvestigationRiskScoreResponse>(
    `/investigations/${id}/risk-score`,
  );
}

export async function getInvestigationCoverage(
  id: string,
): Promise<InvestigationCoverageResponse> {
  return request<InvestigationCoverageResponse>(
    `/investigations/${id}/coverage`,
  );
}

export async function getInvestigationRecommendations(
  id: string,
): Promise<InvestigationRecommendationsResponse> {
  return request<InvestigationRecommendationsResponse>(
    `/investigations/${id}/recommendations`,
  );
}

export async function updateInvestigationStage(
  id: string,
  stage: InvestigationStage,
  reason: string,
): Promise<Investigation> {
  return request<Investigation>(`/investigations/${id}/stage`, {
    method: "PATCH",
    body: JSON.stringify({ stage, reason }),
  });
}

export async function updateInvestigation(
  id: string,
  body: InvestigationUpdateRequest,
): Promise<Investigation> {
  return request<Investigation>(`/investigations/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function updateInvestigationState(
  id: string,
  state: Investigation["status"],
  reason: string,
): Promise<Investigation> {
  return request<Investigation>(`/investigations/${id}/state`, {
    method: "PATCH",
    body: JSON.stringify({ state, status: state, reason }),
  });
}

export async function getInvestigationOwnership(
  id: string,
): Promise<InvestigationOwnership> {
  return request<InvestigationOwnership>(`/investigations/${id}/ownership`);
}

export async function updateInvestigationOwnership(
  id: string,
  body: InvestigationOwnershipUpdate,
): Promise<InvestigationOwnership> {
  return request<InvestigationOwnership>(`/investigations/${id}/ownership`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function handoffInvestigation(
  id: string,
  body: InvestigationHandoffRequest,
): Promise<InvestigationHandoff> {
  return request<InvestigationHandoff>(`/investigations/${id}/handoff`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listInvestigationEscalations(
  id: string,
): Promise<InvestigationEscalation[]> {
  return request<InvestigationEscalation[]>(
    `/investigations/${id}/escalations`,
  );
}

export async function escalateInvestigation(
  id: string,
  level: InvestigationEscalation["level"],
  reason: string,
): Promise<InvestigationEscalation> {
  return request<InvestigationEscalation>(`/investigations/${id}/escalate`, {
    method: "POST",
    body: JSON.stringify({ level, reason }),
  });
}

export async function getCollaborationDashboard(): Promise<CollaborationDashboardResponse> {
  return request<CollaborationDashboardResponse>("/dashboard/collaboration");
}

export async function deleteInvestigation(id: string): Promise<void> {
  return request<void>(`/investigations/${id}`, {
    method: "DELETE",
  });
}

export async function getInvestigationPurgeImpact(
  id: string,
): Promise<InvestigationPurgeImpact> {
  return request<InvestigationPurgeImpact>(
    `/investigations/${id}/purge-impact`,
  );
}

export async function purgeInvestigation(id: string): Promise<void> {
  return request<void>(`/investigations/${id}/purge`, {
    method: "DELETE",
  });
}

export async function restoreInvestigation(id: string): Promise<Investigation> {
  return updateInvestigationState(
    id,
    "active",
    "Investigation restored from archive.",
  );
}

export async function listInvestigationMembers(
  investigationId: string,
): Promise<InvestigationMember[]> {
  return request<InvestigationMember[]>(
    `/investigations/${investigationId}/members`,
  );
}

export async function addInvestigationMember(
  investigationId: string,
  body: MemberAddRequest,
): Promise<InvestigationMember> {
  const requestBody: MemberAddRequest = {
    ...body,
    role: body.role === "analyst" ? "collaborator" : body.role,
  };
  return request<InvestigationMember>(
    `/investigations/${investigationId}/members`,
    {
      method: "POST",
      body: JSON.stringify(requestBody),
    },
  );
}

export async function updateInvestigationMember(
  investigationId: string,
  memberId: string,
  body: MemberUpdateRequest,
): Promise<InvestigationMember> {
  return request<InvestigationMember>(
    `/investigations/${investigationId}/members/${memberId}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export async function removeInvestigationMember(
  investigationId: string,
  memberId: string,
): Promise<void> {
  return request<void>(`/investigations/${investigationId}/members/${memberId}`, {
    method: "DELETE",
  });
}

export async function getInvestigationGraph(
  id: string,
): Promise<InvestigationGraphResponse> {
  return request<InvestigationGraphResponse>(`/investigations/${id}/graph`);
}

export async function getInvestigationAnalytics(
  id: string,
): Promise<InvestigationAnalyticsResponse> {
  return request<InvestigationAnalyticsResponse>(`/investigations/${id}/analytics`);
}

export async function getDashboardAnalytics(): Promise<DashboardAnalyticsResponse> {
  return request<DashboardAnalyticsResponse>("/dashboard/analytics");
}

export async function getDashboardMetrics(): Promise<DashboardMetricsResponse> {
  return request<DashboardMetricsResponse>("/dashboard/metrics");
}

export async function getExecutiveDashboard(): Promise<ExecutiveDashboardResponse> {
  return request<ExecutiveDashboardResponse>("/dashboard/executive");
}

export async function getExecutiveReportingDashboard(): Promise<ExecutiveDashboardResponse> {
  return request<ExecutiveDashboardResponse>("/executive/dashboard");
}

export async function getExecutivePosture(): Promise<ExecutivePostureResponse> {
  return request<ExecutivePostureResponse>("/executive/posture");
}

export async function getExecutiveTrends(): Promise<ExecutiveTrendsResponse> {
  return request<ExecutiveTrendsResponse>("/executive/trends");
}

export async function getExecutiveRecommendations(): Promise<ExecutiveRecommendationsResponse> {
  return request<ExecutiveRecommendationsResponse>("/executive/recommendations");
}

export async function getDashboardOverview(): Promise<DashboardOverviewResponse> {
  return request<DashboardOverviewResponse>("/dashboard/overview");
}

export async function getDashboardHighlights(): Promise<DashboardHighlightsResponse> {
  return request<DashboardHighlightsResponse>("/dashboard/highlights");
}

export async function getDashboardTriage(): Promise<DashboardTriageResponse> {
  return request<DashboardTriageResponse>("/dashboard/triage");
}

export async function getInvestigationQueue(
  filters: InvestigationQueueFilters = {},
): Promise<InvestigationQueueResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      params.set(key, String(value));
    }
  });
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<InvestigationQueueResponse>(`/investigations/queue${suffix}`);
}

export async function applyInvestigationBulkAction(
  body: InvestigationBulkRequest,
): Promise<InvestigationBulkResponse> {
  return request<InvestigationBulkResponse>("/investigations/bulk", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function setInvestigationPinned(
  investigationId: string,
  pinned: boolean,
): Promise<{ investigation_id: string; user_id: string; pinned: boolean }> {
  return request(`/investigations/${investigationId}/pin`, {
    method: "PATCH",
    body: JSON.stringify({ pinned }),
  });
}

export async function getAnalystWorkload(): Promise<AnalystWorkloadResponse> {
  return request<AnalystWorkloadResponse>("/analytics/analysts");
}

export async function getDashboardTimeline(filters: {
  actor_id?: string;
  investigation_id?: string;
  event_type?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<DashboardTimelineResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      params.set(key, String(value));
    }
  });
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<DashboardTimelineResponse>(`/dashboard/timeline${suffix}`);
}

export async function listAuditEvents(
  filters: AuditLogFilters = {},
): Promise<AuditLogListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      params.set(key, String(value));
    }
  });
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<AuditLogListResponse>(`/admin/audit${suffix}`);
}

export async function getFeatureAvailability(): Promise<FeatureAvailabilityResponse> {
  return request<FeatureAvailabilityResponse>("/features");
}

export async function getAdminSettings(): Promise<AdminSettingsResponse> {
  return request<AdminSettingsResponse>("/admin/settings");
}

export async function updateAdminSettings(
  body: AdminSettingsUpdate,
): Promise<AdminSettingsResponse> {
  return request<AdminSettingsResponse>("/admin/settings", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function updateAdminFeatureFlags(
  featureFlags: FeatureFlagSettings,
): Promise<FeatureAvailabilityResponse> {
  return request<FeatureAvailabilityResponse>("/admin/feature-flags", {
    method: "PATCH",
    body: JSON.stringify({ feature_flags: featureFlags }),
  });
}

export async function getAdminRetention(): Promise<RetentionStatusResponse> {
  return request<RetentionStatusResponse>("/admin/retention");
}

export async function updateAdminRetention(
  retention: RetentionSettings,
): Promise<RetentionStatusResponse> {
  return request<RetentionStatusResponse>("/admin/retention", {
    method: "PATCH",
    body: JSON.stringify({ retention }),
  });
}

export async function getAdminOverview(): Promise<AdminOverviewResponse> {
  return request<AdminOverviewResponse>("/admin/overview");
}

export async function getAdminQaStatus(): Promise<AdminQaStatusResponse> {
  return request<AdminQaStatusResponse>("/admin/qa/status");
}

export async function listAdminUsers(
  filters: AdminUserFilters = {},
): Promise<AdminUserListResponse> {
  const params = new URLSearchParams();
  if (filters.role) {
    params.set("role", filters.role);
  }
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.search?.trim()) {
    params.set("search", filters.search.trim());
  }
  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));
  return request<AdminUserListResponse>(`/admin/users?${params.toString()}`);
}

export async function adminUserAction(
  userId: string,
  action: "approve" | "reject" | "disable" | "reactivate",
): Promise<AdminUserActionResponse> {
  return request<AdminUserActionResponse>(`/admin/users/${userId}/${action}`, {
    method: "POST",
  });
}

export async function updateAdminUserRole(
  userId: string,
  role: PlatformUserRole,
): Promise<AdminUserActionResponse> {
  return request<AdminUserActionResponse>(`/admin/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export async function listNotifications(
  filters: NotificationFilters = {},
): Promise<NotificationListResponse> {
  const params = new URLSearchParams();
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.severity) {
    params.set("severity", filters.severity);
  }
  if (filters.notification_type) {
    params.set("notification_type", filters.notification_type);
  }
  if (filters.investigation_id) {
    params.set("investigation_id", filters.investigation_id);
  }
  if (filters.engagement_id) {
    params.set("engagement_id", filters.engagement_id);
  }
  if (typeof filters.limit === "number") {
    params.set("limit", String(filters.limit));
  }
  if (typeof filters.offset === "number") {
    params.set("offset", String(filters.offset));
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<NotificationListResponse>(`/notifications${suffix}`);
}

export async function getNotificationUnreadCount(): Promise<NotificationUnreadCountResponse> {
  return request<NotificationUnreadCountResponse>("/notifications/unread-count");
}

export async function markNotificationRead(
  notificationId: string,
): Promise<NotificationActionResponse> {
  return request<NotificationActionResponse>(
    `/notifications/${notificationId}/read`,
    { method: "PATCH" },
  );
}

export async function dismissNotification(
  notificationId: string,
): Promise<NotificationActionResponse> {
  return request<NotificationActionResponse>(
    `/notifications/${notificationId}/dismiss`,
    { method: "PATCH" },
  );
}

export async function markAllNotificationsRead(): Promise<NotificationMarkAllReadResponse> {
  return request<NotificationMarkAllReadResponse>("/notifications/mark-all-read", {
    method: "POST",
  });
}

export async function globalSearch(
  filters: GlobalSearchFilters = {},
): Promise<GlobalSearchResponse> {
  const params = new URLSearchParams();
  if (filters.q?.trim()) {
    params.set("q", filters.q.trim());
  }
  if (filters.type) {
    params.set("type", filters.type);
  }
  if (typeof filters.limit === "number") {
    params.set("limit", String(filters.limit));
  }
  if (typeof filters.offset === "number") {
    params.set("offset", String(filters.offset));
  }
  if (filters.include_archived) {
    params.set("include_archived", "true");
  }
  if (filters.investigation_id) {
    params.set("investigation_id", filters.investigation_id);
  }
  if (filters.engagement_id) {
    params.set("engagement_id", filters.engagement_id);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<GlobalSearchResponse>(`/search${suffix}`);
}

export async function listSavedViews(filters: {
  view_type?: SavedViewType | "";
  pinned?: boolean;
} = {}): Promise<SavedViewListResponse> {
  const params = new URLSearchParams();
  if (filters.view_type) {
    params.set("view_type", filters.view_type);
  }
  if (typeof filters.pinned === "boolean") {
    params.set("pinned", String(filters.pinned));
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<SavedViewListResponse>(`/saved-views${suffix}`);
}

export async function createSavedView(
  body: SavedViewCreateRequest,
): Promise<SavedView> {
  return request<SavedView>("/saved-views", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateSavedView(
  savedViewId: string,
  body: SavedViewUpdateRequest,
): Promise<SavedView> {
  return request<SavedView>(`/saved-views/${savedViewId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteSavedView(savedViewId: string): Promise<void> {
  return request<void>(`/saved-views/${savedViewId}`, { method: "DELETE" });
}

export async function pinSavedView(savedViewId: string): Promise<SavedView> {
  return request<SavedView>(`/saved-views/${savedViewId}/pin`, {
    method: "POST",
  });
}

export async function unpinSavedView(savedViewId: string): Promise<SavedView> {
  return request<SavedView>(`/saved-views/${savedViewId}/unpin`, {
    method: "POST",
  });
}

export async function setDefaultSavedView(savedViewId: string): Promise<SavedView> {
  return request<SavedView>(`/saved-views/${savedViewId}/set-default`, {
    method: "POST",
  });
}

export async function getDataQualityOverview(): Promise<DataQualityOverviewResponse> {
  return request<DataQualityOverviewResponse>("/admin/data-quality/overview");
}

export async function runDataQualityScan(): Promise<DataQualityScanResponse> {
  return request<DataQualityScanResponse>("/admin/data-quality/run", {
    method: "POST",
  });
}

export async function listDataQualityIssues(
  filters: DataQualityIssueFilters = {},
): Promise<DataQualityIssueListResponse> {
  const params = new URLSearchParams();
  if (filters.severity) params.set("severity", filters.severity);
  if (filters.status) params.set("status", filters.status);
  if (filters.issue_type?.trim()) params.set("issue_type", filters.issue_type.trim());
  if (filters.entity_type) params.set("entity_type", filters.entity_type);
  if (filters.investigation_id) {
    params.set("investigation_id", filters.investigation_id);
  }
  if (filters.engagement_id) params.set("engagement_id", filters.engagement_id);
  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));
  return request<DataQualityIssueListResponse>(
    `/admin/data-quality/issues?${params.toString()}`,
  );
}

export async function getDataQualityIssue(issueId: string): Promise<DataQualityIssue> {
  return request<DataQualityIssue>(`/admin/data-quality/issues/${issueId}`);
}

export async function updateDataQualityIssueStatus(
  issueId: string,
  action: "acknowledge" | "ignore" | "resolve",
): Promise<DataQualityIssue> {
  return request<DataQualityIssue>(
    `/admin/data-quality/issues/${issueId}/${action}`,
    { method: "PATCH" },
  );
}

export async function runMaintenanceDryRun(): Promise<MaintenanceDryRunResponse> {
  return request<MaintenanceDryRunResponse>("/admin/maintenance/dry-run", {
    method: "POST",
  });
}

export async function archiveStaleNotifications(
  olderThanDays = 90,
): Promise<StaleNotificationArchiveResponse> {
  return request<StaleNotificationArchiveResponse>(
    "/admin/maintenance/archive-stale-notifications",
    {
      method: "POST",
      body: JSON.stringify({ older_than_days: olderThanDays }),
    },
  );
}

export async function getOperationsStatus(): Promise<OperationsStatusResponse> {
  return request<OperationsStatusResponse>("/operations/status");
}

export async function getMonitoringOverview(): Promise<MonitoringOverviewResponse> {
  return request<MonitoringOverviewResponse>("/monitoring/overview");
}

export async function listAgentTokens(): Promise<{ total: number; items: EnrollmentToken[] }> { return request("/monitoring/agent-tokens"); }
export async function createAgentToken(body: { name: string; description?: string; allowed_cidr?: string; max_enrollments?: number; expires_at: string }): Promise<EnrollmentToken> { return request("/monitoring/agent-tokens", { method: "POST", body: JSON.stringify(body) }); }
export async function revokeAgentToken(id: string): Promise<EnrollmentToken> { return request(`/monitoring/agent-tokens/${id}/revoke`, { method: "POST" }); }
export async function rotateAgentToken(id: string): Promise<EnrollmentToken> { return request(`/monitoring/agent-tokens/${id}/rotate`, { method: "POST" }); }
export async function listEndpointAgents(): Promise<AgentInventoryResponse> { return request("/monitoring/agents"); }
export async function updateEndpointAgent(id: string, body: Partial<Pick<AgentInventoryItem, "monitoring_enabled" | "is_authorized" | "owner" | "notes" | "criticality">>): Promise<AgentInventoryItem> { return request(`/monitoring/agents/${id}`, { method: "PATCH", body: JSON.stringify(body) }); }
export async function listAssetGroups(): Promise<{ total: number; items: AssetGroup[] }> { return request("/monitoring/asset-groups"); }
export async function createAssetGroup(body: { name: string; description?: string; asset_ids: string[] }): Promise<AssetGroup> { return request("/monitoring/asset-groups", { method: "POST", body: JSON.stringify(body) }); }
export async function updateAssetGroup(id: string, body: Partial<Pick<AssetGroup, "name" | "description" | "asset_ids">>): Promise<AssetGroup> { return request(`/monitoring/asset-groups/${id}`, { method: "PATCH", body: JSON.stringify(body) }); }
export async function deleteAssetGroup(id: string): Promise<void> { return request(`/monitoring/asset-groups/${id}`, { method: "DELETE" }); }
export async function listServiceBaselines(): Promise<{ total: number; items: ServiceBaseline[] }> { return request("/monitoring/service-baselines"); }
export async function createServiceBaseline(body: { name: string; asset_id?: string; group_id?: string; expected_ports: number[]; allowed_ports: number[] }): Promise<ServiceBaseline> { return request("/monitoring/service-baselines", { method: "POST", body: JSON.stringify(body) }); }
export async function deleteServiceBaseline(id: string): Promise<void> { return request(`/monitoring/service-baselines/${id}`, { method: "DELETE" }); }

export async function listMonitoringTriage(filters: {
  status?: MonitoringTriageStatus;
  severity?: "info" | "success" | "warning" | "critical";
  source?: string;
  asset_id?: string;
} = {}): Promise<MonitoringTriageListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  const query = params.toString();
  return request<MonitoringTriageListResponse>(`/monitoring/triage${query ? `?${query}` : ""}`);
}

export async function updateMonitoringTriage(
  alertId: string,
  body: { status?: MonitoringTriageStatus; notes?: string | null; resolution_summary?: string | null },
): Promise<MonitoringTriageItem> {
  return request<MonitoringTriageItem>(`/monitoring/triage/${alertId}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function assignMonitoringTriage(alertId: string, ownerId: string | null): Promise<MonitoringTriageItem> {
  return request<MonitoringTriageItem>(`/monitoring/triage/${alertId}/assign`, { method: "POST", body: JSON.stringify({ owner_id: ownerId }) });
}

export async function resolveMonitoringTriage(alertId: string, resolution: string): Promise<MonitoringTriageItem> {
  return request<MonitoringTriageItem>(`/monitoring/triage/${alertId}/resolve`, { method: "POST", body: JSON.stringify({ resolution_summary: resolution }) });
}

export async function falsePositiveMonitoringTriage(alertId: string, resolution: string): Promise<MonitoringTriageItem> {
  return request<MonitoringTriageItem>(`/monitoring/triage/${alertId}/false-positive`, { method: "POST", body: JSON.stringify({ resolution_summary: resolution }) });
}

export async function muteMonitoringTriage(alertId: string, reason: string): Promise<MonitoringTriageItem> {
  return request<MonitoringTriageItem>(`/monitoring/triage/${alertId}/mute`, { method: "POST", body: JSON.stringify({ reason }) });
}

export async function listMonitoringPolicies(): Promise<MonitoringPolicyListResponse> {
  return request<MonitoringPolicyListResponse>("/monitoring/policies");
}
export async function updateMonitoringPolicy(id: string, body: Partial<MonitoringPolicy>): Promise<MonitoringPolicy> {
  return request<MonitoringPolicy>(`/monitoring/policies/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}
export async function listMaintenanceWindows(): Promise<MaintenanceWindowListResponse> {
  return request<MaintenanceWindowListResponse>("/monitoring/maintenance-windows");
}
export async function createMaintenanceWindow(body: Pick<MaintenanceWindow, "title" | "start_time" | "end_time" | "affected_assets" | "affected_services" | "suppress_alerts" | "reason">): Promise<MaintenanceWindow> {
  return request<MaintenanceWindow>("/monitoring/maintenance-windows", { method: "POST", body: JSON.stringify(body) });
}
export async function suppressMonitoringAlert(id: string, reason: string): Promise<AlertSuppressionResponse> {
  return request<AlertSuppressionResponse>(`/monitoring/alerts/${id}/suppress`, { method: "POST", body: JSON.stringify({ reason }) });
}
export async function unsuppressMonitoringAlert(id: string): Promise<AlertSuppressionResponse> {
  return request<AlertSuppressionResponse>(`/monitoring/alerts/${id}/unsuppress`, { method: "POST" });
}

export async function listLanAssets(): Promise<LanAssetListResponse> {
  return request<LanAssetListResponse>("/monitoring/lan/assets");
}

export async function getLanAsset(assetId: string): Promise<LanAsset> {
  return request<LanAsset>(`/monitoring/lan/assets/${assetId}`);
}

export async function updateLanAsset(
  assetId: string,
  body: Partial<Pick<LanAsset, "hostname" | "vendor" | "asset_type" | "notes" | "is_authorized" | "monitoring_enabled">>,
): Promise<LanAsset> {
  return request<LanAsset>(`/monitoring/lan/assets/${assetId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function discoverLan(cidr?: string): Promise<LanDiscoveryResponse> {
  return request<LanDiscoveryResponse>("/monitoring/lan/discover", {
    method: "POST",
    body: JSON.stringify(cidr ? { cidr } : {}),
  });
}

export async function listLanTelemetry(assetId: string): Promise<LanTelemetryListResponse> {
  return request<LanTelemetryListResponse>(`/monitoring/lan/assets/${assetId}/telemetry`);
}

export async function getEndpointPostureOverview(): Promise<EndpointPostureOverview> {
  return request<EndpointPostureOverview>("/monitoring/posture/overview");
}

export async function getEndpointPosture(assetId: string): Promise<EndpointSecurityPosture> {
  return request<EndpointSecurityPosture>(`/monitoring/lan/assets/${assetId}/posture`);
}

export async function assessEndpointPosture(assetId: string): Promise<EndpointSecurityPosture> {
  return request<EndpointSecurityPosture>(`/monitoring/lan/assets/${assetId}/posture/assess`, { method: "POST" });
}

export async function listEndpointRecommendations(filters: {
  status?: EndpointRecommendationStatus;
  severity?: string;
  asset_id?: string;
} = {}): Promise<EndpointRecommendationListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  const query = params.toString();
  return request<EndpointRecommendationListResponse>(`/monitoring/recommendations${query ? `?${query}` : ""}`);
}

export async function updateEndpointRecommendation(
  id: string,
  body: { severity?: string; notes?: string | null },
): Promise<EndpointRecommendation> {
  return request<EndpointRecommendation>(`/monitoring/recommendations/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function acknowledgeEndpointRecommendation(id: string, notes?: string): Promise<EndpointRecommendation> {
  return request<EndpointRecommendation>(`/monitoring/recommendations/${id}/acknowledge`, { method: "POST", body: JSON.stringify({ notes: notes || null }) });
}

export async function resolveEndpointRecommendation(id: string, notes?: string): Promise<EndpointRecommendation> {
  return request<EndpointRecommendation>(`/monitoring/recommendations/${id}/resolve`, { method: "POST", body: JSON.stringify({ notes: notes || null }) });
}

export async function listLanServices(assetId: string): Promise<LanServiceListResponse> {
  return request<LanServiceListResponse>(`/monitoring/lan/assets/${assetId}/services`);
}

export async function runLanServiceCheck(assetId: string): Promise<LanServiceCheckResponse> {
  return request<LanServiceCheckResponse>(`/monitoring/lan/assets/${assetId}/service-check`, { method: "POST" });
}

export async function getMonitoringActivation(): Promise<MonitoringActivationStatus> {
  return request<MonitoringActivationStatus>("/monitoring/activation");
}

export async function getTargetServiceCheck(targetId: string): Promise<TargetServiceCheckStatus> {
  return request<TargetServiceCheckStatus>(`/monitoring/targets/${targetId}/service-check`);
}

export async function runTargetServiceCheck(targetId: string): Promise<LanServiceCheckResponse> {
  return request<LanServiceCheckResponse>(`/monitoring/targets/${targetId}/service-check`, { method: "POST" });
}

export async function listMonitoringChanges(filters: {
  asset_id?: string;
  event_type?: string;
  severity?: MonitoringChangeSeverity;
  acknowledgement?: "acknowledged" | "unacknowledged";
  date_from?: string;
  date_to?: string;
} = {}): Promise<MonitoringChangeListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  const query = params.toString();
  return request<MonitoringChangeListResponse>(`/monitoring/changes${query ? `?${query}` : ""}`);
}

export async function getMonitoringChangesOverview(): Promise<MonitoringChangeOverview> {
  return request<MonitoringChangeOverview>("/monitoring/changes/overview");
}

export async function acknowledgeMonitoringChange(changeId: string): Promise<{ id: string; acknowledged_at: string }> {
  return request(`/monitoring/changes/${changeId}/acknowledge`, { method: "PATCH" });
}

export async function getLanAssetHistory(assetId: string): Promise<AssetMonitoringHistory> {
  return request<AssetMonitoringHistory>(`/monitoring/lan/assets/${assetId}/history`);
}

export async function getLanServiceHistory(assetId: string): Promise<ServiceHistoryListResponse> {
  return request<ServiceHistoryListResponse>(`/monitoring/lan/assets/${assetId}/service-history`);
}

export async function updateLanAssetCriticality(
  assetId: string,
  body: Pick<LanAsset, "criticality"> & Partial<Pick<LanAsset, "owner" | "business_function" | "environment" | "notes">>,
): Promise<LanAsset> {
  return request<LanAsset>(`/monitoring/lan/assets/${assetId}/criticality`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function listVulnerabilityBaseline(): Promise<VulnerabilityBaselineListResponse> {
  return request<VulnerabilityBaselineListResponse>("/monitoring/vulnerabilities");
}

export async function getVulnerabilityBaselineOverview(): Promise<VulnerabilityBaselineOverview> {
  return request<VulnerabilityBaselineOverview>("/monitoring/vulnerabilities/overview");
}

export async function runVulnerabilityBaseline(): Promise<VulnerabilityBaselineRunResponse> {
  return request<VulnerabilityBaselineRunResponse>("/monitoring/vulnerabilities/run-baseline", { method: "POST" });
}

export async function updateVulnerabilityBaselineFinding(
  findingId: string,
  body: Partial<{ status: VulnerabilityBaselineStatus; remediation_owner: string | null; remediation_due_date: string | null }>,
): Promise<VulnerabilityBaselineFinding> {
  return request<VulnerabilityBaselineFinding>(`/monitoring/vulnerabilities/${findingId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function getOperationsEnvironment(): Promise<EnvironmentValidationResponse> {
  return request<EnvironmentValidationResponse>("/operations/environment");
}

export async function downloadOperationsDiagnostics(
  format: "json" | "zip",
): Promise<FileDownloadResult> {
  return requestBlob(
    `/operations/diagnostics?format=${format}`,
    `raventech-diagnostics.${format}`,
    true,
  );
}

export async function downloadOperationsBackup(
  format: "json" | "zip",
): Promise<FileDownloadResult> {
  return requestBlob(
    `/operations/backup?format=${format}`,
    `raventech-backup.${format}`,
    true,
  );
}

export async function validateRestoreBackup(
  body: RestoreValidationRequest,
): Promise<RestoreValidationResponse> {
  return request<RestoreValidationResponse>("/operations/restore/validate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function seedDemoWorkspace(): Promise<DemoSeedResponse> {
  return request<DemoSeedResponse>("/admin/demo/seed", {
    method: "POST",
  });
}

export async function clearDemoWorkspace(): Promise<DemoSeedResponse> {
  return request<DemoSeedResponse>("/admin/demo/clear", {
    method: "DELETE",
  });
}

export async function listNotes(
  investigationId: string,
  filters: {
    includeArchived?: boolean;
    noteType?: string;
    search?: string;
  } = {},
): Promise<InvestigationNoteListResponse> {
  const params = new URLSearchParams();
  if (filters.includeArchived) {
    params.set("include_archived", "true");
  }
  if (filters.noteType) {
    params.set("note_type", filters.noteType);
  }
  if (filters.search?.trim()) {
    params.set("search", filters.search.trim());
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<InvestigationNoteListResponse>(
    `/investigations/${investigationId}/notes${suffix}`,
  );
}

export async function createNote(
  investigationId: string,
  body: InvestigationNoteCreateRequest,
): Promise<InvestigationNoteListResponse["items"][number]> {
  return request<InvestigationNoteListResponse["items"][number]>(
    `/investigations/${investigationId}/notes`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function updateNote(
  investigationId: string,
  noteId: string,
  body: InvestigationNoteUpdateRequest,
): Promise<InvestigationNoteListResponse["items"][number]> {
  return request<InvestigationNoteListResponse["items"][number]>(
    `/investigations/${investigationId}/notes/${noteId}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export async function deleteNote(
  _investigationId: string,
  noteId: string,
): Promise<void> {
  return request<void>(`/notes/${noteId}`, {
    method: "DELETE",
  });
}

export async function listBookmarks(
  investigationId: string,
): Promise<EvidenceBookmarkListResponse> {
  return request<EvidenceBookmarkListResponse>(
    `/investigations/${investigationId}/bookmarks`,
  );
}

export async function createBookmark(
  investigationId: string,
  body: EvidenceBookmarkCreateRequest,
): Promise<EvidenceBookmark> {
  return request<EvidenceBookmark>(
    `/investigations/${investigationId}/bookmarks`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function deleteBookmark(bookmarkId: string): Promise<void> {
  return request<void>(`/bookmarks/${bookmarkId}`, { method: "DELETE" });
}

export async function listTags(): Promise<InvestigationTagListResponse> {
  return request<InvestigationTagListResponse>("/tags");
}

export async function createTag(body: {
  name: string;
  color: string;
}): Promise<InvestigationTag> {
  return request<InvestigationTag>("/tags", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getInvestigationTags(
  investigationId: string,
): Promise<InvestigationTagListResponse> {
  return request<InvestigationTagListResponse>(
    `/investigations/${investigationId}/tags`,
  );
}

export async function updateInvestigationTags(
  investigationId: string,
  tagIds: string[],
): Promise<InvestigationTagListResponse> {
  return request<InvestigationTagListResponse>(
    `/investigations/${investigationId}/tags`,
    {
      method: "PATCH",
      body: JSON.stringify({ tag_ids: tagIds }),
    },
  );
}

export async function updateInvestigationPriority(
  investigationId: string,
  body: InvestigationPriorityUpdateRequest,
): Promise<InvestigationPriorityResponse> {
  return request<InvestigationPriorityResponse>(
    `/investigations/${investigationId}/priority`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export async function generateInvestigationSummary(
  investigationId: string,
): Promise<InvestigationSummaryResponse> {
  return request<InvestigationSummaryResponse>(
    `/investigations/${investigationId}/summary`,
    { method: "POST" },
  );
}

export async function listTasks(
  investigationId: string,
  includeArchived = false,
): Promise<InvestigationTaskListResponse> {
  const suffix = includeArchived ? "?include_archived=true" : "";
  return request<InvestigationTaskListResponse>(
    `/investigations/${investigationId}/tasks${suffix}`,
  );
}

export async function createTask(
  investigationId: string,
  body: InvestigationTaskCreateRequest,
): Promise<InvestigationTaskListResponse["items"][number]> {
  return request<InvestigationTaskListResponse["items"][number]>(
    `/investigations/${investigationId}/tasks`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function updateTask(
  investigationId: string,
  taskId: string,
  body: InvestigationTaskUpdateRequest,
): Promise<InvestigationTaskListResponse["items"][number]> {
  return request<InvestigationTaskListResponse["items"][number]>(
    `/investigations/${investigationId}/tasks/${taskId}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export async function assignTask(
  taskId: string,
  assignedTo: string,
): Promise<InvestigationTaskListResponse["items"][number]> {
  return request<InvestigationTaskListResponse["items"][number]>(
    `/tasks/${taskId}/assign`,
    {
      method: "PATCH",
      body: JSON.stringify({ assigned_to: assignedTo }),
    },
  );
}

export async function deleteTask(
  investigationId: string,
  taskId: string,
): Promise<void> {
  return request<void>(`/investigations/${investigationId}/tasks/${taskId}`, {
    method: "DELETE",
  });
}

export async function listEvidence(
  investigationId: string,
): Promise<InvestigationEvidenceListResponse> {
  return request<InvestigationEvidenceListResponse>(
    `/investigations/${investigationId}/evidence`,
  );
}

export async function listTargets(
  investigationId: string,
): Promise<TargetListResponse> {
  const params = new URLSearchParams({ investigation_id: investigationId });
  return request<TargetListResponse>(`/targets/?${params.toString()}`);
}

export async function createTarget(body: TargetCreateRequest): Promise<Target> {
  return request<Target>("/targets/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function runPassiveRecon({
  investigationId,
  targetType,
  targetValue,
  authorizationStatement,
}: {
  investigationId: string;
  targetType: TargetType;
  targetValue: string;
  authorizationStatement: string;
}): Promise<ReconResponse> {
  return request<ReconResponse>(`/recon/${targetType}`, {
    method: "POST",
    body: JSON.stringify({
      investigation_id: investigationId,
      target: targetValue,
      authorization_statement: authorizationStatement,
    }),
    timeoutMs: 45_000,
  });
}

export async function listFindings(id: string): Promise<Finding[]> {
  return request<Finding[]>(`/investigations/${id}/findings`);
}

export async function generateFindings(id: string): Promise<Finding[]> {
  return request<Finding[]>(`/investigations/${id}/findings/generate`, {
    method: "POST",
  });
}

export async function updateFindingStatus(
  findingId: string,
  body: {
    status: FindingStatus;
    review_notes?: string | null;
    remediation_notes?: string | null;
    validation_notes?: string | null;
  },
): Promise<Finding> {
  return request<Finding>(`/findings/${findingId}/status`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function assignFinding(
  findingId: string,
  body: { assigned_to?: string | null; reviewed_by?: string | null },
): Promise<Finding> {
  return request<Finding>(`/findings/${findingId}/assign`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function listPlaybooks(): Promise<DefensivePlaybook[]> {
  return request<DefensivePlaybook[]>("/playbooks");
}

export async function listFindingPlaybooks(
  findingId: string,
): Promise<FindingPlaybookRecommendation[]> {
  return request<FindingPlaybookRecommendation[]>(
    `/findings/${findingId}/playbooks`,
  );
}

export async function startFindingPlaybook(
  findingId: string,
  playbookId: string,
): Promise<PlaybookRun> {
  return request<PlaybookRun>(
    `/findings/${findingId}/playbooks/${playbookId}/start`,
    { method: "POST" },
  );
}

export async function listPlaybookRuns(
  investigationId: string,
  includeArchived = false,
): Promise<PlaybookRun[]> {
  const suffix = includeArchived ? "?include_archived=true" : "";
  return request<PlaybookRun[]>(
    `/investigations/${investigationId}/playbook-runs${suffix}`,
  );
}

export async function updatePlaybookRun(
  runId: string,
  status: PlaybookRunStatus,
): Promise<PlaybookRun> {
  return request<PlaybookRun>(`/playbook-runs/${runId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function updatePlaybookRunArchive(
  runId: string,
  archived: boolean,
): Promise<PlaybookRun> {
  return request<PlaybookRun>(`/playbook-runs/${runId}`, {
    method: "PATCH",
    body: JSON.stringify({ archived }),
  });
}

export async function updatePlaybookRunStep(
  runId: string,
  stepId: string,
  body: {
    status: PlaybookRunStepStatus;
    analyst_note?: string | null;
  },
): Promise<PlaybookRun> {
  return request<PlaybookRun>(`/playbook-runs/${runId}/steps/${stepId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function updateFindingRemediation(
  findingId: string,
  body: FindingRemediationUpdate,
): Promise<FindingRemediationResponse> {
  return request<FindingRemediationResponse>(
    `/findings/${findingId}/remediation`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export async function getTimeline(
  id: string,
  filters: {
    source?: string;
    event_type?: string;
    analyst_id?: string;
    start_date?: string;
    end_date?: string;
  } = {},
): Promise<TimelineResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value?.trim()) {
      params.set(key, value);
    }
  });
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<TimelineResponse>(`/investigations/${id}/timeline${suffix}`);
}

export async function getCorrelations(id: string): Promise<CorrelationResponse> {
  return request<CorrelationResponse>(`/investigations/${id}/correlations`);
}

export async function getCrossInvestigationCorrelations(
  signalType?: CrossInvestigationSignalType,
): Promise<CrossInvestigationCorrelationResponse> {
  const suffix = signalType
    ? `?${new URLSearchParams({ signal_type: signalType }).toString()}`
    : "";
  return request<CrossInvestigationCorrelationResponse>(
    `/correlations/cross-investigation${suffix}`,
  );
}

export async function listIocs(filters: {
  type?: IOCType;
  confidence?: IOCConfidence;
  q?: string;
  recurringOnly?: boolean;
} = {}): Promise<IOCListResponse> {
  const params = new URLSearchParams();
  if (filters.type) {
    params.set("type", filters.type);
  }
  if (filters.confidence) {
    params.set("confidence", filters.confidence);
  }
  if (filters.q?.trim()) {
    params.set("q", filters.q.trim());
  }
  if (filters.recurringOnly) {
    params.set("recurring_only", "true");
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<IOCListResponse>(`/iocs${suffix}`);
}

export async function getIocDetail(iocId: string): Promise<IOCDetail> {
  return request<IOCDetail>(`/iocs/${iocId}`);
}

export async function getIocCorrelations(): Promise<IOCCorrelationResponse> {
  return request<IOCCorrelationResponse>("/iocs/correlations");
}

export async function getEvidenceIntelligenceOverview(): Promise<EvidenceIntelligenceOverviewResponse> {
  return request<EvidenceIntelligenceOverviewResponse>("/intelligence/overview");
}

export async function getEvidenceIntelligenceEvidence(): Promise<EvidenceIntelligenceEvidenceResponse> {
  return request<EvidenceIntelligenceEvidenceResponse>("/intelligence/evidence");
}

export async function getEvidenceIntelligencePriority(): Promise<EvidenceIntelligencePriorityResponse> {
  return request<EvidenceIntelligencePriorityResponse>("/intelligence/priority");
}

export async function getEvidenceIntelligenceTimeline(): Promise<EvidenceIntelligenceTimelineResponse> {
  return request<EvidenceIntelligenceTimelineResponse>("/intelligence/timeline");
}

export async function getEvidenceIntelligenceIocs(): Promise<EvidenceIntelligenceIOCResponse> {
  return request<EvidenceIntelligenceIOCResponse>("/intelligence/iocs");
}

export async function getThreatOverview(): Promise<ThreatOverviewResponse> {
  return request<ThreatOverviewResponse>("/threat/overview");
}

export async function getThreatIndicators(): Promise<ThreatIndicatorListResponse> {
  return request<ThreatIndicatorListResponse>("/threat/indicators");
}

export async function getThreatCampaigns(): Promise<ThreatCampaignListResponse> {
  return request<ThreatCampaignListResponse>("/threat/campaigns");
}

export async function getThreatGroups(): Promise<ThreatGroupListResponse> {
  return request<ThreatGroupListResponse>("/threat/groups");
}

export async function getThreatTechniques(): Promise<ThreatTechniqueListResponse> {
  return request<ThreatTechniqueListResponse>("/threat/techniques");
}

export async function getThreatInfrastructure(): Promise<ThreatInfrastructureResponse> {
  return request<ThreatInfrastructureResponse>("/threat/infrastructure");
}

export async function getThreatTimeline(): Promise<ThreatTimelineResponse> {
  return request<ThreatTimelineResponse>("/threat/timeline");
}

export async function listInvestigationIocs(
  investigationId: string,
): Promise<IOCListResponse> {
  return request<IOCListResponse>(`/investigations/${investigationId}/iocs`);
}

export async function getInvestigationPrioritization(
  investigationId: string,
): Promise<InvestigationPrioritizationResponse> {
  return request<InvestigationPrioritizationResponse>(
    `/investigations/${investigationId}/prioritization`,
  );
}

export async function listReports(
  id: string,
  includeArchived = false,
): Promise<ReportListResponse> {
  const suffix = includeArchived ? "?include_archived=true" : "";
  return request<ReportListResponse>(`/investigations/${id}/reports${suffix}`);
}

export async function getCaseReview(
  investigationId: string,
): Promise<CaseReviewResponse> {
  return request<CaseReviewResponse>(`/investigations/${investigationId}/review`);
}

export async function submitCaseReview(
  investigationId: string,
  notes?: string,
): Promise<CaseReviewResponse> {
  return request<CaseReviewResponse>(
    `/investigations/${investigationId}/review/submit`,
    {
      method: "POST",
      body: JSON.stringify({ notes }),
    },
  );
}

export async function decideCaseReview(
  investigationId: string,
  body: { decision: "approve" | "reject" | "request_changes"; notes: string },
): Promise<CaseReviewResponse> {
  return request<CaseReviewResponse>(
    `/investigations/${investigationId}/review/decision`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function closeCase(
  investigationId: string,
  body: { closure_reason: string; override_reason?: string | null },
): Promise<CaseReviewResponse> {
  return request<CaseReviewResponse>(`/investigations/${investigationId}/close`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getCaseClosure(
  investigationId: string,
): Promise<CaseClosureResponse> {
  return request<CaseClosureResponse>(`/investigations/${investigationId}/closure`);
}

export async function generateClosureChecklist(
  investigationId: string,
): Promise<CaseClosureResponse> {
  return request<CaseClosureResponse>(
    `/investigations/${investigationId}/closure/generate-checklist`,
    { method: "POST" },
  );
}

export async function updateCaseClosure(
  investigationId: string,
  body: {
    closure_summary?: string | null;
    final_risk_rating?: CaseFinalRiskRating | null;
  },
): Promise<CaseClosureResponse> {
  return request<CaseClosureResponse>(`/investigations/${investigationId}/closure`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function submitCaseClosureReview(
  investigationId: string,
  body: { closure_summary?: string | null },
): Promise<CaseClosureResponse> {
  return request<CaseClosureResponse>(
    `/investigations/${investigationId}/closure/submit-review`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function approveCaseClosure(
  investigationId: string,
): Promise<CaseClosureResponse> {
  return request<CaseClosureResponse>(
    `/investigations/${investigationId}/closure/approve`,
    { method: "POST" },
  );
}

export async function closeCaseClosure(
  investigationId: string,
  body: { closure_summary: string; override_reason?: string | null },
): Promise<CaseClosureResponse> {
  return request<CaseClosureResponse>(
    `/investigations/${investigationId}/closure/close`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function reopenCaseClosure(
  investigationId: string,
): Promise<CaseClosureResponse> {
  return request<CaseClosureResponse>(
    `/investigations/${investigationId}/closure/reopen`,
    { method: "POST" },
  );
}

export async function updateClosureChecklistItem(
  investigationId: string,
  itemId: string,
  body: { status: CaseClosureChecklistStatus; description?: string | null },
): Promise<CaseClosureChecklistItem> {
  return request<CaseClosureChecklistItem>(
    `/investigations/${investigationId}/closure/checklist/${itemId}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
}

export async function listCaseDeliverables(
  investigationId: string,
  includeArchived = false,
): Promise<CaseDeliverableListResponse> {
  const suffix = includeArchived ? "?include_archived=true" : "";
  return request<CaseDeliverableListResponse>(
    `/investigations/${investigationId}/deliverables${suffix}`,
  );
}

export async function createCaseDeliverable(
  investigationId: string,
  body: {
    title: string;
    deliverable_type: CaseDeliverableType;
    status?: CaseDeliverableStatus;
    report_id?: string | null;
    export_format?: ReportFormat | null;
    file_reference?: string | null;
  },
): Promise<CaseDeliverable> {
  return request<CaseDeliverable>(`/investigations/${investigationId}/deliverables`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateCaseDeliverable(
  investigationId: string,
  deliverableId: string,
  body: {
    title?: string;
    deliverable_type?: CaseDeliverableType;
    status?: CaseDeliverableStatus;
    report_id?: string | null;
    export_format?: ReportFormat | null;
    file_reference?: string | null;
  },
): Promise<CaseDeliverable> {
  return request<CaseDeliverable>(
    `/investigations/${investigationId}/deliverables/${deliverableId}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
}

export async function archiveCaseDeliverable(
  investigationId: string,
  deliverableId: string,
): Promise<void> {
  await request<void>(
    `/investigations/${investigationId}/deliverables/${deliverableId}`,
    { method: "DELETE" },
  );
}

export async function createCasePackageManifest(
  investigationId: string,
): Promise<CasePackageManifestResponse> {
  return request<CasePackageManifestResponse>(
    `/investigations/${investigationId}/deliverables/package`,
    { method: "POST" },
  );
}

export async function getEvidenceCompleteness(
  investigationId: string,
): Promise<EvidenceCompletenessResponse> {
  return request<EvidenceCompletenessResponse>(
    `/investigations/${investigationId}/completeness`,
  );
}

export async function submitReportApproval(
  reportId: string,
  notes?: string,
): Promise<ReportApprovalResponse> {
  return request<ReportApprovalResponse>(`/reports/${reportId}/submit-approval`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
}

export async function decideReportApproval(
  reportId: string,
  body: { decision: "approve" | "reject"; notes: string },
): Promise<ReportApprovalResponse> {
  return request<ReportApprovalResponse>(`/reports/${reportId}/approval-decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function submitRemediationValidation(
  findingId: string,
  body: { validation_owner?: string | null; validation_notes?: string | null } = {},
): Promise<RemediationValidationResponse> {
  return request<RemediationValidationResponse>(
    `/findings/${findingId}/validation/submit`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function decideRemediationValidation(
  findingId: string,
  body: {
    decision: "validate" | "fail" | "accept_risk";
    notes: string;
    failure_reason?: string | null;
  },
): Promise<RemediationValidationResponse> {
  return request<RemediationValidationResponse>(
    `/findings/${findingId}/validation/decision`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function getReviewBoard(filters: {
  status?: string;
  assigned_reviewer?: string;
  priority?: string;
  risk?: string;
  due_date_before?: string;
} = {}): Promise<ReviewBoardResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      params.set(key, String(value));
    }
  });
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<ReviewBoardResponse>(`/review-board${suffix}`);
}

export async function listReportingCenterReports(
  filters: ReportingCenterFilters = {},
): Promise<ReportingCenterResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      params.set(key, String(value));
    }
  });
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<ReportingCenterResponse>(`/reports${suffix}`);
}

export async function listReportTemplates(
  includeInactive = false,
): Promise<ReportTemplateListResponse> {
  const suffix = includeInactive ? "?include_inactive=true" : "";
  return request<ReportTemplateListResponse>(`/report-templates${suffix}`);
}

export async function createReportTemplate(
  body: ReportTemplateCreateRequest,
): Promise<ReportTemplate> {
  return request<ReportTemplate>("/report-templates", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateReportTemplate(
  templateId: string,
  body: ReportTemplateUpdateRequest,
): Promise<ReportTemplate> {
  return request<ReportTemplate>(`/report-templates/${templateId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deactivateReportTemplate(
  templateId: string,
): Promise<ReportTemplate> {
  return request<ReportTemplate>(`/report-templates/${templateId}`, {
    method: "DELETE",
  });
}

export async function createReport(
  investigationId: string,
  body: ReportCreateRequest,
): Promise<ReportSummary> {
  return request<ReportSummary>(`/investigations/${investigationId}/reports`, {
    method: "POST",
    body: JSON.stringify(body),
    timeoutMs: 45_000,
  });
}

export async function previewReportQuality(
  investigationId: string,
  reportType: ReportCreateRequest["report_type"],
  templateId?: string | null,
): Promise<ReportQualityResponse> {
  const params = new URLSearchParams({ report_type: reportType });
  if (templateId) {
    params.set("template_id", templateId);
  }
  return request<ReportQualityResponse>(
    `/investigations/${investigationId}/reports/quality?${params.toString()}`,
  );
}

export async function getReportQuality(
  reportId: string,
): Promise<ReportQualityResponse> {
  return request<ReportQualityResponse>(`/reports/${reportId}/quality`);
}

export async function bulkGenerateReports(
  body: ReportBulkGenerateRequest,
): Promise<ReportBulkGenerateResponse> {
  return request<ReportBulkGenerateResponse>("/reports/bulk-generate", {
    method: "POST",
    body: JSON.stringify(body),
    timeoutMs: 90_000,
  });
}

export async function archiveReport(
  reportId: string,
): Promise<ReportActionResponse> {
  return request<ReportActionResponse>(`/reports/${reportId}/archive`, {
    method: "PATCH",
  });
}

export async function restoreReport(
  reportId: string,
): Promise<ReportActionResponse> {
  return request<ReportActionResponse>(`/reports/${reportId}/restore`, {
    method: "PATCH",
  });
}

export async function retryReport(
  reportId: string,
): Promise<ReportActionResponse> {
  return request<ReportActionResponse>(`/reports/${reportId}/retry`, {
    method: "POST",
    timeoutMs: 45_000,
  });
}

export async function downloadReport(
  reportId: string,
  format: ReportFormat,
): Promise<FileDownloadResult> {
  return requestBlob(
    `/reports/${reportId}/download?format=${format}`,
    `report-${reportId}.${format}`,
  );
}

export async function searchKnowledge(query: string): Promise<KnowledgeSearchResponse> {
  const params = new URLSearchParams({ q: query, mode: "hybrid", limit: "10" });
  return request<KnowledgeSearchResponse>(`/knowledge/search?${params.toString()}`);
}

export async function getDetectionKnowledge(
  kind?: "sigma" | "yara",
): Promise<DetectionKnowledgeResponse> {
  const suffix = kind ? `?kind=${kind}` : "";
  return request<DetectionKnowledgeResponse>(`/knowledge/detections${suffix}`);
}

export async function getFrameworkKnowledge(): Promise<FrameworkKnowledgeResponse> {
  return request<FrameworkKnowledgeResponse>("/knowledge/frameworks");
}

export async function getIocGuidance(query?: string): Promise<IOCGuidanceResponse> {
  const suffix = query?.trim()
    ? `?${new URLSearchParams({ q: query.trim() }).toString()}`
    : "";
  return request<IOCGuidanceResponse>(`/knowledge/ioc-guidance${suffix}`);
}

export async function analyzeInvestigation(id: string): Promise<AnalysisResponse> {
  return request<AnalysisResponse>("/analysis/investigation", {
    method: "POST",
    body: JSON.stringify({ investigation_id: id }),
  });
}

interface RequestInitWithAuth extends RequestInit {
  skipAuth?: boolean;
  timeoutMs?: number;
}

async function request<T>(
  path: string,
  options: RequestInitWithAuth = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: buildHeaders(options),
      credentials: "include",
      signal: controller.signal,
    });
    if (!response.ok) {
      const error = await apiError(response, path);
      handleAuthFailure(error, options);
      throw error;
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        "The request timed out before the backend responded.",
        408,
        path,
        {
          category: "Request timeout",
          detail: "Request timed out before the backend responded.",
          suggestion: "Refresh the page or retry after the backend is healthy.",
        },
      );
    }
    if (error instanceof TypeError) {
      throw backendUnavailableError(error, path);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function requestBlob(
  path: string,
  fallbackFilename: string,
  allowJson = false,
): Promise<FileDownloadResult> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: buildHeaders({}),
      credentials: "include",
      signal: controller.signal,
    });
    if (!response.ok) {
      const error = await apiError(response, path);
      handleAuthFailure(error, {});
      throw error;
    }
    const contentType = response.headers.get("content-type") ?? "";
    if (!allowJson && contentType.toLowerCase().includes("application/json")) {
      throw await apiError(response, path);
    }
    const blob = await response.blob();
    return {
      blob,
      filename: contentDispositionFilename(response) ?? fallbackFilename,
      mimeType: contentType || blob.type || "application/octet-stream",
      handledExternally: false,
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        "The download request timed out before the backend responded.",
        408,
        path,
        {
          category: "Request timeout",
          detail: "Request timed out before the backend responded.",
          suggestion: "Retry the download after the backend is healthy.",
        },
      );
    }
    if (error instanceof TypeError) {
      if (await backendIsReachableAfterDownloadHandoff()) {
        return {
          blob: null,
          filename: fallbackFilename,
          mimeType: "application/octet-stream",
          handledExternally: true,
        };
      }
      throw backendUnavailableError(error, path);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function contentDispositionFilename(response: Response): string | null {
  const disposition = response.headers.get("content-disposition");
  if (!disposition) {
    return null;
  }
  const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch?.[1]) {
    try {
      return sanitizeDownloadFilename(decodeURIComponent(encodedMatch[1]));
    } catch {
      return sanitizeDownloadFilename(encodedMatch[1]);
    }
  }
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  return filenameMatch?.[1]
    ? sanitizeDownloadFilename(filenameMatch[1])
    : null;
}

function sanitizeDownloadFilename(filename: string): string {
  const sanitized = filename.trim().replace(/[\\/:*?"<>|]/g, "-");
  return sanitized || "download";
}

async function backendIsReachableAfterDownloadHandoff(): Promise<boolean> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 3_000);
  try {
    const response = await fetch(`${API_ROOT_URL}/health/live`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function requestRoot<T>(
  path: string,
  options: RequestInitWithAuth = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );
  try {
    const response = await fetch(`${API_ROOT_URL}${path}`, {
      ...options,
      headers: buildHeaders(options),
      credentials: "include",
      signal: controller.signal,
    });
    if (!response.ok) {
      const error = await apiError(response, path);
      handleAuthFailure(error, options);
      throw error;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        "The request timed out before the backend responded.",
        408,
        path,
        {
          category: "Request timeout",
          detail: "Request timed out before the backend responded.",
          suggestion: "Refresh the page or retry after the backend is healthy.",
        },
      );
    }
    if (error instanceof TypeError) {
      throw backendUnavailableError(error, path);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function buildHeaders(options: RequestInitWithAuth): HeadersInit {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");
  const token = getAccessToken();
  if (!options.skipAuth && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

async function apiError(response: Response, path: string): Promise<ApiError> {
  let detail = `Request failed with status ${response.status}`;
  let requestId: string | undefined;
  try {
    const payload = (await response.json()) as {
      detail?: unknown;
      error?: {
        message?: unknown;
        detail?: unknown;
        request_id?: unknown;
      };
    };
    const structuredDetail = payload.error?.detail ?? payload.error?.message;
    if (typeof structuredDetail === "string") {
      detail = structuredDetail;
    } else if (
      typeof structuredDetail === "object" &&
      structuredDetail !== null &&
      "message" in structuredDetail
    ) {
      detail = String(structuredDetail.message);
    } else if (typeof payload.detail === "string") {
      detail = payload.detail;
    } else if (
      typeof payload.detail === "object" &&
      payload.detail !== null &&
      "message" in payload.detail
    ) {
      detail = String(payload.detail.message);
    } else if (Array.isArray(payload.detail)) {
      detail = payload.detail
        .map((item) => {
          if (typeof item === "object" && item !== null && "msg" in item) {
            return String(item.msg);
          }
          return String(item);
        })
        .join("; ");
    }
    if (typeof payload.error?.request_id === "string") {
      requestId = payload.error.request_id;
    }
  } catch {
    // Keep the status-based fallback.
  }
  const { category, suggestion, userMessage } = apiErrorCopy(
    response.status,
    detail,
  );
  return new ApiError(userMessage, response.status, path, {
    category,
    detail,
    requestId,
    suggestion,
  });
}

function handleAuthFailure(error: ApiError, options: RequestInitWithAuth): void {
  if (error.status === 401 && !options.skipAuth) {
    clearTokens();
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
}

function backendUnavailableError(error: TypeError, path: string): ApiError {
  const reason = error.message.includes("abort")
    ? "The request was interrupted before the backend responded."
    : "The browser could not reach the backend API.";
  return new ApiError(
    "Backend temporarily unavailable.",
    0,
    path,
    {
      category: "Backend unreachable",
      detail: `${reason} API base URL: ${API_BASE_URL}.`,
      suggestion: "Confirm Docker is healthy and the backend URL is correct.",
    },
  );
}

function apiErrorCopy(
  status: number,
  detail: string,
): { category: string; suggestion: string; userMessage: string } {
  const category =
    status === 401
      ? "Authentication required"
      : status === 403
        ? "Permission denied"
        : status === 404
          ? "Endpoint or resource not found"
          : status >= 500
            ? "Backend exception"
            : "Request validation failed";
  const suggestion =
    status === 401
      ? "Sign in again."
      : status === 403
        ? "Use an authorized account or request access."
        : status === 404
          ? "Confirm the investigation or resource still exists."
          : status >= 500
            ? "Check backend logs and retry after the service is healthy."
            : "Review the request inputs and try again.";
  const userMessage =
    status === 401
      ? "Authentication required. Sign in again."
      : status === 403
        ? "This action requires additional permissions."
        : status === 404
          ? "The requested item could not be found."
          : status === 409
            ? detail || "This request conflicts with existing data."
            : status === 422
              ? detail || "Review the request inputs and try again."
              : status >= 500
                ? "Backend temporarily unavailable."
                : detail;
  return { category, suggestion, userMessage };
}

export function apiBaseUrl(): string {
  return API_BASE_URL;
}
