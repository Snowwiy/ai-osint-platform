const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function safeUuid(value) {
  return typeof value === "string" && UUID.test(value) ? value : null;
}

/** Resolve only known evidence classes to fixed in-app destinations. */
export function resolveAiEvidenceDestination(evidenceId, scope = {}) {
  if (typeof evidenceId !== "string") return null;
  const separator = evidenceId.indexOf(":");
  if (separator < 1) return null;
  const kind = evidenceId.slice(0, separator).toUpperCase();
  const sourceId = evidenceId.slice(separator + 1);
  const investigationId = safeUuid(scope?.investigation_id);
  const assetId = safeUuid(scope?.asset_id);
  const alertId = safeUuid(scope?.alert_id);

  if (kind === "INVESTIGATION") {
    const id = safeUuid(sourceId);
    return id ? `/investigations/${id}` : null;
  }
  if (kind === "FINDING") {
    return investigationId ? `/investigations/${investigationId}/findings` : "/investigations";
  }
  if (kind === "TIMELINE") {
    if (investigationId) return `/investigations/${investigationId}/timeline`;
    if (alertId) return "/notifications";
    if (assetId) return "/monitoring";
    return "/operations/timeline";
  }
  if (kind === "ALERT") return "/notifications";
  if (kind === "KNOWLEDGE") return "/knowledge";
  if (kind === "OPERATIONS") return "/admin/operations";
  if ([
    "HOST-METRIC",
    "DESKTOP-INVENTORY-PROCESS",
    "DESKTOP-INVENTORY-SERVICE",
    "LAN-ASSET",
    "SERVICE",
    "ENDPOINT",
    "POSTURE",
  ].includes(kind)) return "/monitoring";
  return null;
}
