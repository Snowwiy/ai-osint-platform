import { ChevronDown, PlayCircle } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import {
  checkEngagementScope,
  createTarget,
  getInvestigation,
  listTargets,
  runPassiveRecon,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type {
  NormalizedEntity,
  ReconError,
  ReconResponse,
  Target,
  TargetType,
} from "../types";

const targetTypes: TargetType[] = ["domain", "ip", "url"];
const MIN_AUTH_LENGTH = 100;

interface ReconState {
  status: "completed" | "completed_with_warnings" | "failed";
  response?: ReconResponse;
  error?: string;
}

export function TargetsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const queryClient = useQueryClient();
  const [targetType, setTargetType] = useState<TargetType>("domain");
  const [targetValue, setTargetValue] = useState("");
  const [authorizationStatement, setAuthorizationStatement] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [scopeWarning, setScopeWarning] = useState<string | null>(null);
  const [reconResults, setReconResults] = useState<Record<string, ReconState>>({});

  const investigation = useQuery({
    queryKey: ["investigation", investigationId],
    queryFn: () => getInvestigation(investigationId),
  });
  const targets = useQuery({
    queryKey: ["targets", investigationId],
    queryFn: () => listTargets(investigationId),
  });

  const cleanTarget = targetValue.trim();
  const cleanAuth = authorizationStatement.trim();
  const hasValidTarget = cleanTarget.length > 0;
  const hasValidAuth = cleanAuth.length >= MIN_AUTH_LENGTH;

  const createMutation = useMutation({
    mutationFn: createTarget,
    onSuccess: async () => {
      setTargetValue("");
      setAuthorizationStatement("");
      setValidationError(null);
      setScopeWarning(null);
      await queryClient.invalidateQueries({ queryKey: ["targets", investigationId] });
    },
  });

  const canSubmit = hasValidTarget && hasValidAuth && !createMutation.isPending;

  const reconMutation = useMutation({
    mutationFn: async (target: Target) => {
      const auth = authorizationForTarget(
        target,
        investigation.data?.authorization_statement,
      );
      return runPassiveRecon({
        investigationId,
        targetType: target.target_type,
        targetValue: target.target_value,
        authorizationStatement: auth,
      });
    },
    onSuccess: async (response, target) => {
      setReconResults((current) => ({
        ...current,
        [target.id]: {
          status: reconDisplayStatus(response),
          response,
        },
      }));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["graph", investigationId] }),
        queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
        queryClient.invalidateQueries({ queryKey: ["correlations", investigationId] }),
      ]);
    },
    onError: (error, target) => {
      setReconResults((current) => ({
        ...current,
        [target.id]: {
          status: "failed",
          response: current[target.id]?.response,
          error: "The latest passive recon attempt could not complete. Retry when the provider is available.",
        },
      }));
    },
  });

  const isLoading = investigation.isLoading || targets.isLoading;
  const error = investigation.error ?? targets.error;
  const targetItems = useMemo(() => targets.data?.items ?? [], [targets.data?.items]);
  const targetCounts = useMemo(
    () =>
      targetTypes.map((type) => ({
        type,
        count: targetItems.filter((target) => target.target_type === type).length,
      })),
    [targetItems],
  );

  async function handleCreate(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!hasValidTarget) {
      setValidationError("Enter a domain, IP address, or URL before adding a target.");
      return;
    }
    if (!hasValidAuth) {
      setValidationError(
        `Authorization statement needs at least ${MIN_AUTH_LENGTH} characters.`,
      );
      return;
    }
    setValidationError(null);
    setScopeWarning(null);
    const engagementId = investigation.data?.engagement_id;
    if (engagementId) {
      try {
        const result = await checkEngagementScope(engagementId, {
          value: cleanTarget,
          scope_type:
            targetType === "domain" || targetType === "ip" ? targetType : undefined,
        });
        if (result.status !== "in_scope") {
          setScopeWarning(result.warning);
        }
      } catch (error) {
        setScopeWarning(
          error instanceof Error
            ? `Scope check unavailable: ${error.message}`
            : "Scope check is unavailable. Review engagement scope manually.",
        );
      }
    }
    createMutation.mutate({
      investigation_id: investigationId,
      target_type: targetType,
      target_value: cleanTarget,
      label: cleanTarget,
      notes: cleanAuth,
    });
  }

  if (isLoading) {
    return <LoadingBlock label="Loading targets" />;
  }
  if (error) {
    return <ErrorBlock message={error} />;
  }

  return (
    <>
      <PageHeader title="Targets" eyebrow="Passive recon workflow" />
      <InvestigationTabs />

      <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <h2 className="text-lg font-semibold">Add target</h2>
          <form onSubmit={handleCreate} className="mt-4 space-y-4">
            <div>
              <label className="block text-sm text-raven-muted" htmlFor="target-type">
                Target type
              </label>
              <select
                id="target-type"
                value={targetType}
                onChange={(event) => setTargetType(event.target.value as TargetType)}
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
              >
                {targetTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm text-raven-muted" htmlFor="target-value">
                Target value
              </label>
              <input
                id="target-value"
                value={targetValue}
                onChange={(event) => {
                  setTargetValue(event.target.value);
                  setValidationError(null);
                  setScopeWarning(null);
                }}
                placeholder={targetPlaceholder(targetType)}
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
              />
              <p className="mt-1 text-xs leading-5 text-raven-muted">
                Passive recon accepts one authorized domain, IP address, or URL.
              </p>
            </div>

            <div>
              <div className="flex items-center justify-between gap-3">
                <label
                  className="block text-sm text-raven-muted"
                  htmlFor="target-auth"
                >
                  Authorization statement
                </label>
                <span
                  className={[
                    "text-xs",
                    hasValidAuth ? "text-raven-emerald" : "text-raven-muted",
                  ].join(" ")}
                >
                  {cleanAuth.length}/{MIN_AUTH_LENGTH}
                </span>
              </div>
              <textarea
                id="target-auth"
                value={authorizationStatement}
                onChange={(event) => {
                  setAuthorizationStatement(event.target.value);
                  setValidationError(null);
                }}
                rows={5}
                placeholder="Document who authorized this passive recon, the approved scope, and any reference or ticket number."
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
              />
              <p className="mt-1 text-xs leading-5 text-raven-muted">
                This text is stored with the target and reused when you run passive
                recon from this page.
              </p>
            </div>

            {validationError ?? createMutation.error?.message ? (
              <div className="rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
                {validationError ?? createMutation.error?.message}
              </div>
            ) : null}

            {scopeWarning ? (
              <div className="rounded-md border border-amber-300/30 bg-amber-400/10 p-3 text-sm leading-6 text-amber-100">
                {scopeWarning}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={!canSubmit}
              className="w-full rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {createMutation.isPending ? "Adding target" : "Add target"}
            </button>
          </form>

          <div className="mt-6 grid grid-cols-3 gap-2">
            {targetCounts.map((item) => (
              <div
                key={item.type}
                className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
              >
                <p className="text-xs uppercase text-raven-muted">{item.type}</p>
                <p className="mt-1 text-xl font-semibold">{item.count}</p>
              </div>
            ))}
          </div>
        </section>

        <section>
          {targetItems.length ? (
            <div className="space-y-4">
              {targetItems.map((target) => {
                const result = reconResults[target.id];
                const isRunning =
                  reconMutation.isPending && reconMutation.variables?.id === target.id;
                return (
                  <article
                    key={target.id}
                    className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
                  >
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <p className="text-xs uppercase tracking-wide text-raven-cyan">
                          {target.target_type} target
                        </p>
                        <LongValue
                          value={target.target_value}
                          className="mt-1 font-semibold"
                          maxLength={72}
                        />
                        <p className="mt-2 text-sm text-raven-muted">
                          Added {new Date(target.created_at).toLocaleString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => reconMutation.mutate(target)}
                        disabled={reconMutation.isPending}
                        title={reconMutation.isPending && !isRunning ? "Another passive recon run is already in progress." : isRunning ? "This authorized recon run is in progress." : "Run passive provider checks for this authorized target."}
                        className="inline-flex items-center justify-center gap-2 rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text hover:border-raven-violet disabled:opacity-60"
                      >
                        <PlayCircle className="h-4 w-4" aria-hidden="true" />
                        {isRunning
                          ? "Running"
                          : `Run ${target.target_type} recon`}
                      </button>
                    </div>

                    <div className="mt-4">
                      {result ? <ReconResultPanel result={result} /> : null}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <EmptyBlock
              title="No authorized targets"
              message="Targets identify the domain, IP address, or URL included in this investigation."
              nextStep="Add a domain, IP, or URL that you are authorized to assess."
              permission="Viewers cannot add targets or run passive recon."
            />
          )}
        </section>
      </div>
    </>
  );
}

function ReconResultPanel({ result }: { result: ReconState }): JSX.Element {
  if (result.error && !result.response) {
    return (
      <div className="rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
        {result.error}
      </div>
    );
  }
  const response = result.response;
  if (!response) {
    return <></>;
  }

  const entities = uniqueEntities(response.entities);
  const grouped = groupEntities(entities);
  const errors = uniqueErrors(response.errors);
  const hasStoredData = entities.length > 0 || response.relationships.length > 0;
  const status = reconDisplayStatus(response);
  const summary = reconSummary(response, hasStoredData, errors.length);

  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      {result.error ? <div className="mb-3 rounded-md border border-amber-300/30 bg-amber-400/10 p-3 text-sm text-amber-100">{result.error} Showing the last successful stored result below.</div> : null}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <StatusPill status={status} />
        <span className="text-raven-muted">
          {response.target_type} recon - {entities.length} unique entities -{" "}
          {response.relationships.length} relationships
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-raven-muted">{summary}</p>

      {errors.length ? (
        <details className="mt-3 rounded-md border border-amber-300/30 bg-amber-400/10">
          <summary className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2 text-sm text-amber-100">
            <span>Partial source failures ({errors.length})</span>
            <span className="text-xs text-amber-100/70">Open details</span>
          </summary>
          <div className="border-t border-amber-300/20 px-3 py-3">
            <div className="flex flex-wrap gap-2">
              {errors.map((error) => (
                <span
                  key={`${error.source}-${error.message}`}
                  className="rounded border border-amber-300/30 px-2 py-1 text-xs text-amber-100"
                >
                  {providerLabel(error.source)}
                </span>
              ))}
            </div>
            <ul className="mt-3 space-y-2 text-sm text-amber-100/85">
              {errors.map((error) => (
                <li key={`${error.source}-${error.message}`}>
                  <span className="font-medium">{providerLabel(error.source)}:</span>{" "}
                  {friendlyErrorMessage(error)}
                </li>
              ))}
            </ul>
          </div>
        </details>
      ) : null}

      {grouped.length ? (
        <div className="mt-3 grid gap-3">
          {grouped.map((group) => (
            <div
              key={group.entityType}
              className="rounded border border-raven-border bg-raven-bg/40 p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs uppercase tracking-wide text-raven-cyan">
                  {group.entityType}
                </p>
                <span className="text-xs text-raven-muted">
                  {group.items.length} stored
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {group.items.slice(0, 8).map((entity) => (
                  <div
                    key={`${entity.entity_type}-${entity.value}`}
                    className="max-w-full rounded border border-raven-border px-2 py-1 text-xs text-raven-muted"
                  >
                    <LongValue value={entity.value} maxLength={56} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <details className="mt-3">
        <summary className="flex cursor-pointer items-center gap-2 text-sm text-raven-cyan">
          <ChevronDown className="h-4 w-4" aria-hidden="true" />
          Raw JSON
        </summary>
        <pre className="mt-3 max-h-96 overflow-auto rounded-md bg-raven-bg p-3 text-xs text-raven-muted">
          {JSON.stringify(response, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function StatusPill({
  status,
}: {
  status: ReconState["status"];
}): JSX.Element {
  const classes: Record<ReconState["status"], string> = {
    completed: "border-emerald-400/30 bg-emerald-400/10 text-emerald-100",
    completed_with_warnings:
      "border-amber-300/30 bg-amber-400/10 text-amber-100",
    failed: "border-rose-400/30 bg-rose-500/10 text-rose-100",
  };
  return (
    <span
      className={[
        "rounded border px-2 py-1 text-xs font-medium",
        classes[status],
      ].join(" ")}
    >
      {status}
    </span>
  );
}

function reconDisplayStatus(response: ReconResponse): ReconState["status"] {
  const hasStoredData =
    response.entities.length > 0 || response.relationships.length > 0;
  if (response.errors.length > 0 && hasStoredData) {
    return "completed_with_warnings";
  }
  if (response.status === "failed" && !hasStoredData) {
    return "failed";
  }
  if (response.status === "partial") {
    return hasStoredData ? "completed_with_warnings" : "failed";
  }
  return "completed";
}

function reconSummary(
  response: ReconResponse,
  hasStoredData: boolean,
  errorCount: number,
): string {
  if (!errorCount) {
    return "Passive recon completed and stored normalized entities.";
  }
  if (hasStoredData && response.target_type === "ip") {
    return "IP recon stored valid entities, but some enrichment providers failed.";
  }
  if (hasStoredData) {
    return "Recon stored valid entities, with warnings from some passive sources.";
  }
  return "Recon did not store entities because all required passive sources failed.";
}

function uniqueEntities(entities: NormalizedEntity[]): NormalizedEntity[] {
  const seen = new Set<string>();
  return entities.filter((entity) => {
    const key = `${entity.entity_type}:${entity.value}`.toLowerCase();
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function groupEntities(
  entities: NormalizedEntity[],
): Array<{ entityType: string; items: NormalizedEntity[] }> {
  const groups = new Map<string, NormalizedEntity[]>();
  for (const entity of entities) {
    const items = groups.get(entity.entity_type) ?? [];
    items.push(entity);
    groups.set(entity.entity_type, items);
  }
  return Array.from(groups.entries())
    .map(([entityType, items]) => ({ entityType, items }))
    .sort((left, right) =>
      String(left.entityType ?? "").localeCompare(String(right.entityType ?? "")),
    );
}

function uniqueErrors(errors: ReconError[]): ReconError[] {
  const seen = new Set<string>();
  return errors.filter((error) => {
    const key = `${error.source}:${friendlyErrorMessage(error)}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function providerLabel(source: string): string {
  const labels: Record<string, string> = {
    "ip-rdap": "IP RDAP",
    rdap: "RDAP",
    "crt.sh": "crt.sh certificates",
    certificates: "Certificates",
    dns: "DNS",
    http: "HTTP/TLS",
  };
  return labels[source] ?? source.replace(/[-_]/g, " ");
}

function friendlyErrorMessage(error: ReconError): string {
  const raw = error.message || "Provider did not return data.";
  if (raw === "provider_timeout") return "Provider timed out; retry is safe and stored results were preserved.";
  if (raw === "provider_http_error") return "Provider returned an HTTP or connectivity error.";
  if (raw === "provider_parse_error") return "Provider returned an unreadable response.";
  if (raw === "provider_error") return "Provider failed without exposing internal details.";
  if (raw.includes("timed out") || raw.toLowerCase().includes("timeout")) {
    return "Request timed out.";
  }
  if (raw.includes("HTTPStatusError")) {
    return "Provider returned an HTTP error.";
  }
  return raw;
}

function targetPlaceholder(type: TargetType): string {
  if (type === "ip") {
    return "203.0.113.10";
  }
  if (type === "url") {
    return "https://example.com/login";
  }
  return "example.com";
}

function authorizationForTarget(
  target: Target,
  investigationAuthorization: string | undefined,
): string {
  const targetAuthorization = target.notes?.trim();
  if (targetAuthorization && targetAuthorization.length >= MIN_AUTH_LENGTH) {
    return targetAuthorization;
  }
  return investigationAuthorization ?? "";
}
