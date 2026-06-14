import type {
  AnalysisResponse,
  AuditLogFilters,
  AuditLogListResponse,
  CorrelationResponse,
  DashboardAnalyticsResponse,
  DashboardMetricsResponse,
  DefensivePlaybook,
  EvidenceBookmark,
  EvidenceBookmarkCreateRequest,
  EvidenceBookmarkListResponse,
  Finding,
  FindingPlaybookRecommendation,
  FindingRemediationResponse,
  FindingRemediationUpdate,
  FindingStatus,
  HealthResponse,
  InvestigationEvidenceListResponse,
  InvestigationAnalyticsResponse,
  Investigation,
  InvestigationCreateRequest,
  InvestigationGraphResponse,
  InvestigationListResponse,
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
  PlaybookRun,
  PlaybookRunStatus,
  PlaybookRunStepStatus,
  ReportCreateRequest,
  ReportFormat,
  ReconResponse,
  ReportListResponse,
  ReportSummary,
  Target,
  TargetCreateRequest,
  TargetListResponse,
  TargetType,
  TimelineResponse,
  TokenResponse,
  UserProfile,
} from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const API_ROOT_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, "");

const ACCESS_TOKEN_KEY = "raventech.accessToken";
const REFRESH_TOKEN_KEY = "raventech.refreshToken";
const DEFAULT_TIMEOUT_MS = 30_000;
export const AUTH_EXPIRED_EVENT = "raventech:auth-expired";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly endpoint?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
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
  const response = await request<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
    skipAuth: true,
  });
  setTokens(response.access_token, response.refresh_token);
  return response;
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
  return requestRoot<HealthResponse>("/health/ready", { skipAuth: true });
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

export async function updateInvestigation(
  id: string,
  body: InvestigationUpdateRequest,
): Promise<Investigation> {
  return request<Investigation>(`/investigations/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function deleteInvestigation(id: string): Promise<void> {
  return request<void>(`/investigations/${id}`, {
    method: "DELETE",
  });
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
  return request<InvestigationMember>(
    `/investigations/${investigationId}/members`,
    {
      method: "POST",
      body: JSON.stringify(body),
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
): Promise<InvestigationTaskListResponse> {
  return request<InvestigationTaskListResponse>(
    `/investigations/${investigationId}/tasks`,
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
): Promise<PlaybookRun[]> {
  return request<PlaybookRun[]>(
    `/investigations/${investigationId}/playbook-runs`,
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

export async function getTimeline(id: string): Promise<TimelineResponse> {
  return request<TimelineResponse>(`/investigations/${id}/timeline`);
}

export async function getCorrelations(id: string): Promise<CorrelationResponse> {
  return request<CorrelationResponse>(`/investigations/${id}/correlations`);
}

export async function listReports(id: string): Promise<ReportListResponse> {
  return request<ReportListResponse>(`/investigations/${id}/reports`);
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

export async function downloadReport(
  reportId: string,
  format: ReportFormat,
): Promise<Blob> {
  return requestBlob(`/reports/${reportId}/download?format=${format}`);
}

export async function searchKnowledge(query: string): Promise<KnowledgeSearchResponse> {
  const params = new URLSearchParams({ q: query, mode: "hybrid", limit: "10" });
  return request<KnowledgeSearchResponse>(`/knowledge/search?${params.toString()}`);
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
        formatApiError(path, 408, "Request timed out before the backend responded."),
        408,
        path,
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

async function requestBlob(path: string): Promise<Blob> {
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
    return response.blob();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        formatApiError(path, 408, "Request timed out before the backend responded."),
        408,
        path,
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
        formatApiError(path, 408, "Request timed out before the backend responded."),
        408,
        path,
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
    } else if (typeof payload.detail === "string") {
      detail = payload.detail;
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
      detail = `${detail} (request ${payload.error.request_id})`;
    }
  } catch {
    // Keep the status-based fallback.
  }
  return new ApiError(
    formatApiError(path, response.status, detail),
    response.status,
    path,
  );
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
    [
      `Endpoint: ${path}`,
      "Status: unavailable",
      "Category: Backend unreachable",
      `Detail: ${reason} API base URL: ${API_BASE_URL}.`,
      "Suggested action: confirm Docker is healthy and the backend URL is correct.",
    ].join("\n"),
    0,
    path,
  );
}

function formatApiError(path: string, status: number, detail: string): string {
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
  return [
    `Endpoint: ${path}`,
    `Status: ${status}`,
    `Category: ${category}`,
    `Detail: ${detail}`,
    `Suggested action: ${suggestion}`,
  ].join("\n");
}

export function apiBaseUrl(): string {
  return API_BASE_URL;
}
