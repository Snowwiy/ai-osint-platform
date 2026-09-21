export type ServiceHealth = "healthy" | "warning" | "critical" | "neutral";
export type LocalServiceExpectation = { expectedState: "running" | "stopped"; required: boolean; criticality: "low" | "medium" | "high" | "critical"; notes: string };

export function localServiceHealth(state: string, expectation?: LocalServiceExpectation, stale = false): { health: ServiceHealth; reason: string } {
  if (stale) return { health: "warning", reason: "Service inventory has not refreshed within the expected interval." };
  if (["starting", "stopping", "paused"].includes(state)) return { health: "warning", reason: `Service is ${state}; wait for a stable state or review it locally.` };
  if (!expectation) return { health: "neutral", reason: "No expected state is configured for this service." };
  if (state === expectation.expectedState) return { health: state === "running" ? "healthy" : "neutral", reason: "Service state matches the configured baseline." };
  if (expectation.expectedState === "running" && state === "stopped" && (expectation.required || expectation.criticality === "critical")) return { health: "critical", reason: "Required or critical expected service is not running." };
  return { health: "warning", reason: "Service state differs from the configured baseline." };
}

export function coreServiceHealth(status: string, required: boolean, stale = false): { health: ServiceHealth; reason: string } {
  if (!required && status === "optional") return { health: "neutral", reason: "Compatibility component is not required in this runtime." };
  if (stale) return { health: "warning", reason: "Telemetry has not been refreshed within the expected interval." };
  if (["healthy", "running", "connected"].includes(status)) return { health: "healthy", reason: "Component is reporting healthy." };
  if (["down", "unavailable", "stopped", "offline"].includes(status)) return { health: required ? "critical" : "warning", reason: required ? "Required component is unavailable." : "Optional component is unavailable." };
  return { health: required ? "warning" : "neutral", reason: "Component health is unknown; confirm its status manually." };
}

export const serviceHealthIcon: Record<ServiceHealth, string> = { healthy: "✓", warning: "!", critical: "×", neutral: "•" };
export const serviceHealthTone: Record<ServiceHealth, string> = {
  healthy: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200",
  warning: "border-amber-400/40 bg-amber-500/10 text-amber-100",
  critical: "border-rose-400/40 bg-rose-500/10 text-rose-100",
  neutral: "border-raven-border bg-raven-panelSoft text-raven-text",
};
