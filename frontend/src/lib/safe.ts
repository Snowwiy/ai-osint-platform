export function safeArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

export function safeString(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export function safeNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function safeDate(value: unknown): Date | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function safeLocaleCompare(left: unknown, right: unknown): number {
  return safeString(left).localeCompare(safeString(right));
}

export function safeInternalRoute(value: unknown, fallback = "/"): string {
  const route = safeString(value);
  if (!route.startsWith("/") || route.startsWith("//") || route.includes("\\")) {
    return fallback;
  }
  return route;
}
