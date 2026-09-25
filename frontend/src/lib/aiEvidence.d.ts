export interface AiEvidenceScope {
  investigation_id?: unknown;
  asset_id?: unknown;
  alert_id?: unknown;
}

export function resolveAiEvidenceDestination(
  evidenceId: string,
  scope?: AiEvidenceScope,
): string | null;
