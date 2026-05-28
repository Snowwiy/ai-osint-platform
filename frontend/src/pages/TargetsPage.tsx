import { ChevronDown, PlayCircle } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import {
  createTarget,
  getInvestigation,
  listTargets,
  runPassiveRecon,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type { ReconResponse, Target, TargetType } from "../types";

const targetTypes: TargetType[] = ["domain", "ip", "url"];

interface ReconState {
  status: "success" | "partial" | "failed";
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
  const [reconResults, setReconResults] = useState<Record<string, ReconState>>({});

  const investigation = useQuery({
    queryKey: ["investigation", investigationId],
    queryFn: () => getInvestigation(investigationId),
  });
  const targets = useQuery({
    queryKey: ["targets", investigationId],
    queryFn: () => listTargets(investigationId),
  });

  const createMutation = useMutation({
    mutationFn: createTarget,
    onSuccess: async () => {
      setTargetValue("");
      setAuthorizationStatement("");
      setValidationError(null);
      await queryClient.invalidateQueries({ queryKey: ["targets", investigationId] });
    },
  });

  const reconMutation = useMutation({
    mutationFn: async (target: Target) => {
      const auth = authorizationForTarget(target, investigation.data?.authorization_statement);
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
          status: response.status === "completed" ? "success" : response.status,
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
          error: error instanceof Error ? error.message : "Recon failed",
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

  function handleCreate(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const cleanTarget = targetValue.trim();
    const cleanAuth = authorizationStatement.trim();
    if (!cleanTarget) {
      setValidationError("Target value is required.");
      return;
    }
    if (cleanAuth.length < 100) {
      setValidationError("Authorization statement must be at least 100 characters.");
      return;
    }
    setValidationError(null);
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
    return <ErrorBlock message={error.message} />;
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
                onChange={(event) => setTargetValue(event.target.value)}
                placeholder={targetType === "ip" ? "203.0.113.10" : "example.com"}
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
              />
            </div>

            <div>
              <label className="block text-sm text-raven-muted" htmlFor="target-auth">
                Authorization statement
              </label>
              <textarea
                id="target-auth"
                value={authorizationStatement}
                onChange={(event) => setAuthorizationStatement(event.target.value)}
                rows={5}
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
              />
            </div>

            {validationError ?? createMutation.error?.message ? (
              <div className="rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
                {validationError ?? createMutation.error?.message}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={createMutation.isPending}
              className="w-full rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
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
                      <div>
                        <p className="text-xs uppercase tracking-wide text-raven-cyan">
                          {target.target_type}
                        </p>
                        <h2 className="mt-1 break-all font-semibold">
                          {target.target_value}
                        </h2>
                        <p className="mt-2 text-sm text-raven-muted">
                          Added {new Date(target.created_at).toLocaleString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => reconMutation.mutate(target)}
                        disabled={isRunning}
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
            <EmptyBlock message="No targets are stored yet. Add a domain, IP, or URL to run passive recon." />
          )}
        </section>
      </div>
    </>
  );
}

function ReconResultPanel({ result }: { result: ReconState }): JSX.Element {
  if (result.error) {
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

  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">Recon {response.status}</span>
        <span className="text-raven-muted">
          {response.entities.length} entities · {response.relationships.length} relationships
        </span>
      </div>
      {response.errors.length ? (
        <div className="mt-3 rounded-md border border-amber-300/30 bg-amber-400/10 p-3 text-sm text-amber-100">
          Partial failures: {response.errors.map((error) => error.source).join(", ")}
        </div>
      ) : null}
      {response.entities.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {response.entities.slice(0, 8).map((entity) => (
            <span
              key={`${entity.entity_type}-${entity.value}`}
              className="rounded border border-raven-border px-2 py-1 text-xs text-raven-muted"
            >
              {entity.entity_type}: {entity.value}
            </span>
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

function authorizationForTarget(
  target: Target,
  investigationAuthorization: string | undefined,
): string {
  const targetAuthorization = target.notes?.trim();
  if (targetAuthorization && targetAuthorization.length >= 100) {
    return targetAuthorization;
  }
  return investigationAuthorization ?? "";
}
