import type {
  AnalysisResponse,
  CorrelationResponse,
  Finding,
  Investigation,
  InvestigationGraphResponse,
  InvestigationListResponse,
  KnowledgeSearchResponse,
  ReportListResponse,
  TimelineResponse,
  TokenResponse,
  UserProfile,
} from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

const ACCESS_TOKEN_KEY = "raventech.accessToken";
const REFRESH_TOKEN_KEY = "raventech.refreshToken";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
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

export async function listInvestigations(): Promise<InvestigationListResponse> {
  return request<InvestigationListResponse>("/investigations/");
}

export async function getInvestigation(id: string): Promise<Investigation> {
  return request<Investigation>(`/investigations/${id}`);
}

export async function getInvestigationGraph(
  id: string,
): Promise<InvestigationGraphResponse> {
  return request<InvestigationGraphResponse>(`/investigations/${id}/graph`);
}

export async function listFindings(id: string): Promise<Finding[]> {
  return request<Finding[]>(`/investigations/${id}/findings`);
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

export async function downloadReport(
  reportId: string,
  format: "html" | "md" | "pdf" | "docx",
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
}

async function request<T>(
  path: string,
  options: RequestInitWithAuth = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: buildHeaders(options),
    credentials: "include",
  });
  if (!response.ok) {
    throw await apiError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: buildHeaders({}),
    credentials: "include",
  });
  if (!response.ok) {
    throw await apiError(response);
  }
  return response.blob();
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

async function apiError(response: Response): Promise<ApiError> {
  let message = `Request failed with status ${response.status}`;
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      message = payload.detail;
    }
  } catch {
    // Keep the status-based fallback.
  }
  return new ApiError(message, response.status);
}

export function apiBaseUrl(): string {
  return API_BASE_URL;
}
