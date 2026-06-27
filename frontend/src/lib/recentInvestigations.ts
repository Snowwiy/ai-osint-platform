import type { Investigation } from "../types";

const STORAGE_KEY = "raventech.recent-investigations";
const MAX_ITEMS = 8;

export interface RecentInvestigation {
  id: string;
  title: string;
  status: Investigation["status"];
  stage: Investigation["stage"];
  viewed_at: string;
}

export function rememberInvestigation(investigation: Investigation): void {
  const next: RecentInvestigation = {
    id: investigation.id,
    title: investigation.title,
    status: investigation.status,
    stage: investigation.stage,
    viewed_at: new Date().toISOString(),
  };
  const items = readRecentInvestigations().filter(
    (item) => item.id !== investigation.id,
  );
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([next, ...items].slice(0, MAX_ITEMS)),
    );
  } catch {
    // Local preferences must never block the investigation workspace.
  }
}

export function readRecentInvestigations(): RecentInvestigation[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isRecentInvestigation).slice(0, MAX_ITEMS);
  } catch {
    return [];
  }
}

function isRecentInvestigation(value: unknown): value is RecentInvestigation {
  if (!value || typeof value !== "object") {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    typeof item.id === "string" &&
    typeof item.title === "string" &&
    typeof item.status === "string" &&
    typeof item.stage === "string" &&
    typeof item.viewed_at === "string"
  );
}
