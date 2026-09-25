import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Clock3, RefreshCw, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import {
  compareEvidenceAnalyses,
  getEvidenceAnalysis,
  listEvidenceAnalyses,
  rerunEvidenceAnalysis,
  runEvidenceAnalysis,
} from "../lib/api";
import type {
  EvidenceAnalysisListItem,
  EvidenceAnalysisRecord,
  EvidenceAnalysisRequest,
  EvidenceAnalysisResource,
  EvidenceAnalysisWindow,
  EvidenceAnalysisWorkflow,
} from "../types";

const workflows: Array<{ value: EvidenceAnalysisWorkflow; label: string }> = [
  { value: "host_current", label: "Analyze Server" },
  { value: "host_changes", label: "What Changed" },
  { value: "host_resource", label: "Analyze Resource Usage" },
  { value: "host_services", label: "Analyze Services" },
  { value: "host_ports", label: "Analyze Ports" },
  { value: "lan_current", label: "Analyze LAN" },
  { value: "lan_changes", label: "Analyze LAN Changes" },
  { value: "asset_current", label: "Analyze Asset" },
  { value: "asset_changes", label: "Compare Asset History" },
  { value: "alert_context", label: "Explain Alert" },
  { value: "posture_context", label: "Explain Posture" },
  { value: "investigation_context", label: "Analyze Investigation" },
  { value: "global_attention", label: "Operational Attention Summary" },
];
const windows: EvidenceAnalysisWindow[] = ["15m", "1h", "6h", "12h", "24h", "7d"];
const scopedWorkflows = new Set<EvidenceAnalysisWorkflow>([
  "asset_current", "asset_changes", "alert_context", "posture_context", "investigation_context",
]);

export function EvidenceAnalysisPanel({
  translate,
  isAdmin,
  desktopInventory,
}: {
  translate: (value: string) => string;
  isAdmin: boolean;
  desktopInventory: unknown;
}): JSX.Element {
  const t = translate;
  const queryClient = useQueryClient();
  const [workflow, setWorkflow] = useState<EvidenceAnalysisWorkflow>("host_current");
  const [windowSize, setWindowSize] = useState<EvidenceAnalysisWindow>("1h");
  const [resource, setResource] = useState<EvidenceAnalysisResource>("memory");
  const [scopeId, setScopeId] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [compareId, setCompareId] = useState("");

  const history = useQuery({
    queryKey: ["ai-evidence-analysis-history"],
    queryFn: listEvidenceAnalyses,
    staleTime: 10_000,
  });
  const detail = useQuery({
    queryKey: ["ai-evidence-analysis", selectedId],
    queryFn: () => getEvidenceAnalysis(selectedId),
    enabled: Boolean(selectedId),
  });
  const run = useMutation({
    mutationFn: runEvidenceAnalysis,
    onSuccess: async (value) => {
      setSelectedId(value.id);
      await queryClient.invalidateQueries({ queryKey: ["ai-evidence-analysis-history"] });
    },
  });
  const rerun = useMutation({
    mutationFn: rerunEvidenceAnalysis,
    onSuccess: async (value) => {
      setSelectedId(value.id);
      await queryClient.invalidateQueries({ queryKey: ["ai-evidence-analysis-history"] });
    },
  });
  const compare = useMutation({
    mutationFn: () => compareEvidenceAnalyses(selectedId, compareId),
  });

  const candidateHistory = useMemo(
    () => (history.data ?? []).filter((item) => item.id !== selectedId),
    [history.data, selectedId],
  );
  useEffect(() => {
    if (!candidateHistory.some((item) => item.id === compareId)) {
      setCompareId(candidateHistory[0]?.id ?? "");
    }
  }, [candidateHistory, compareId]);

  const needsScope = scopedWorkflows.has(workflow);
  const validScope = !needsScope || isUuid(scopeId);
  const buildRequest = (): EvidenceAnalysisRequest => ({
    workflow,
    window: windowSize,
    ...(workflow === "host_resource" ? { resource } : {}),
    ...(needsScope ? { scope_id: scopeId.trim() } : {}),
    ...(isAdmin && workflow.startsWith("host_")
      ? { desktop_inventory: safeInventory(desktopInventory) }
      : {}),
  });
  const analysis = detail.data;
  const result = analysis?.result;

  return (
    <section className="overflow-hidden rounded-xl border border-raven-border bg-raven-panel" aria-label={t("Deterministic evidence analysis")}>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-raven-border p-4">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 font-semibold"><Activity size={17} />{t("Evidence analysis")}</h2>
          <p className="mt-1 max-w-3xl text-sm text-raven-muted">{t("Builds a bounded, read-only evidence bundle and deterministic correlations. It can explain and recommend checks, but never takes actions.")}</p>
        </div>
        <div className="flex items-center gap-1 rounded-full border border-raven-border px-2.5 py-1 text-xs text-raven-muted"><ShieldCheck size={14} />{t("No model required")}</div>
      </div>

      <div className="grid gap-3 border-b border-raven-border p-4 md:grid-cols-2 xl:grid-cols-[minmax(190px,1.6fr)_minmax(100px,.7fr)_minmax(130px,.8fr)_minmax(210px,1fr)_auto]">
        <label className="min-w-0 text-xs text-raven-muted">{t("Analysis workflow")}
          <select value={workflow} onChange={(event) => setWorkflow(event.target.value as EvidenceAnalysisWorkflow)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-2 py-2 text-sm text-raven-text">
            {workflows.map((item) => <option key={item.value} value={item.value}>{t(item.label)}</option>)}
          </select>
        </label>
        <label className="text-xs text-raven-muted">{t("Time window")}
          <select value={windowSize} onChange={(event) => setWindowSize(event.target.value as EvidenceAnalysisWindow)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-2 py-2 text-sm text-raven-text">
            {windows.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        {workflow === "host_resource" ? <label className="text-xs text-raven-muted">{t("Resource")}
          <select value={resource} onChange={(event) => setResource(event.target.value as EvidenceAnalysisResource)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-2 py-2 text-sm text-raven-text">
            {(["cpu", "memory", "disk"] as const).map((item) => <option key={item} value={item}>{t(item === "cpu" ? "CPU" : item === "memory" ? "Memory" : "Disk")}</option>)}
          </select>
        </label> : <div className="hidden xl:block" />}
        {needsScope ? <label className="min-w-0 text-xs text-raven-muted">{t("Selected record ID")}
          <input value={scopeId} onChange={(event) => setScopeId(event.target.value)} aria-label={t("Selected record ID")} placeholder={t("Paste an asset, alert, posture, or investigation ID")} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-2 py-2 text-sm text-raven-text" />
        </label> : <div className="hidden xl:block" />}
        <button type="button" onClick={() => run.mutate(buildRequest())} disabled={!validScope || run.isPending} className="inline-flex items-center justify-center gap-2 self-end rounded-md bg-raven-violet px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"><Activity size={15} />{run.isPending ? t("Analyzing") : t("Run analysis")}</button>
      </div>

      {(run.isError || detail.isError || rerun.isError || compare.isError) ? <p role="status" className="px-4 pt-3 text-sm text-amber-300">{t("The evidence analysis request could not be completed. Check access and selected record scope.")}</p> : null}
      {run.data?.deduplicated ? <p role="status" className="px-4 pt-3 text-xs text-raven-muted">{t("Identical evidence already has a saved analysis; the existing result is shown.")}</p> : null}

      <div className="grid min-w-0 gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-w-0 space-y-4">
          {analysis && result ? <>
            <div className="rounded-lg border border-raven-border bg-raven-panelSoft p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold">{t("What RavenTech observed")}</h3>
                <span className="rounded-full border border-raven-border px-2 py-1 text-xs">{t("Confidence")}: {t(result.confidence)}</span>
              </div>
              <p className="mt-2 text-sm leading-6">{result.summary}</p>
              <p className="mt-2 break-all text-[11px] text-raven-muted">{t("Evidence bundle hash")}: {analysis.bundle_sha256}</p>
              <p className="mt-1 text-[11px] text-raven-muted">{analysis.evidence_count} · {t("evidence records")} · {new Date(analysis.generated_at).toLocaleString()}</p>
            </div>
            {Object.keys(result.metrics).length ? <div className="grid gap-2 sm:grid-cols-3">{Object.entries(result.metrics).map(([key, metric]) => <div key={key} className="min-w-0 rounded-lg border border-raven-border p-3"><p className="text-xs uppercase text-raven-muted">{t(key === "cpu" ? "CPU" : key === "memory" ? "Memory" : "Disk")}</p><p className="mt-1 text-lg font-semibold">{typeof metric.current === "number" ? `${metric.current.toFixed(1)}%` : "—"}</p><p className="text-xs text-raven-muted">{t("Trend")}: {t(String(metric.trend ?? "unknown"))}</p><p className="text-xs text-raven-muted">{t("Baseline")}: {t(String(metric.baseline_status ?? "insufficient_data"))}</p></div>)}</div> : null}
            <AnalysisRecords title="Facts" records={result.facts} translate={t} />
            <AnalysisRecords title="Changes" records={result.changes} translate={t} />
            <AnalysisRecords title="Correlations" records={result.correlations} translate={t} />
            <AnalysisRecords title="Hypotheses" records={result.hypotheses} translate={t} />
            <AnalysisRecords title="Manual verification guidance" records={result.recommendations} translate={t} />
            <AnalysisRecords title="Knowledge references" records={result.knowledge} translate={t} />
            {result.data_gaps.length ? <div className="rounded-lg border border-amber-500/30 p-3"><h3 className="text-sm font-semibold">{t("Data gaps and uncertainty")}</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-raven-muted">{result.data_gaps.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div> : null}
          </> : detail.isLoading ? <p className="text-sm text-raven-muted">{t("Loading saved analysis")}</p> : <div className="rounded-lg border border-dashed border-raven-border p-6 text-sm text-raven-muted">{t("Run a deterministic analysis to build a timestamped evidence bundle. No chat model or external provider is called.")}</div>}
        </div>

        <aside className="min-w-0 space-y-3">
          <div className="rounded-lg border border-raven-border p-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold"><Clock3 size={15} />{t("Analysis history")}</h3>
            <div className="mt-2 max-h-64 space-y-1 overflow-y-auto">
              {(history.data ?? []).map((item) => <button key={item.id} type="button" onClick={() => { setSelectedId(item.id); compare.reset(); }} className={`block w-full min-w-0 rounded p-2 text-left text-xs ${item.id === selectedId ? "bg-raven-panelSoft" : "hover:bg-raven-panelSoft"}`}>
                <span className="block truncate font-medium">{t(workflows.find((workflowItem) => workflowItem.value === item.workflow)?.label ?? item.workflow)}</span>
                <span className="block text-raven-muted">{new Date(item.generated_at).toLocaleString()} · {t(item.confidence)} · {item.evidence_count}</span>
              </button>)}
              {!history.data?.length ? <p className="p-2 text-xs text-raven-muted">{t("No saved analyses yet")}</p> : null}
            </div>
            {analysis ? <button type="button" onClick={() => rerun.mutate(analysis.id)} disabled={rerun.isPending} className="mt-2 inline-flex items-center gap-2 rounded border border-raven-border px-2.5 py-1.5 text-xs disabled:opacity-50"><RefreshCw size={13} />{rerun.isPending ? t("Analyzing") : t("Rerun with current evidence")}</button> : null}
          </div>
          {analysis && candidateHistory.length ? <div className="rounded-lg border border-raven-border p-3">
            <h3 className="text-sm font-semibold">{t("Compare with saved analysis")}</h3>
            <select value={compareId} onChange={(event) => setCompareId(event.target.value)} className="mt-2 w-full rounded border border-raven-border bg-raven-bg px-2 py-2 text-xs">
              {candidateHistory.map((item) => <option key={item.id} value={item.id}>{historyLabel(item, t)}</option>)}
            </select>
            <button type="button" onClick={() => compare.mutate()} disabled={!compareId || compare.isPending} className="mt-2 rounded border border-raven-border px-2.5 py-1.5 text-xs disabled:opacity-50">{t("Compare evidence")}</button>
            {compare.data ? <div className="mt-2 text-xs text-raven-muted"><p>{compare.data.summary}</p>{compare.data.differences.map((item) => <p key={item} className="mt-1">• {item}</p>)}</div> : null}
          </div> : null}
          {analysis ? <p className="break-all text-[10px] text-raven-muted">{analysis.id}</p> : null}
        </aside>
      </div>
    </section>
  );
}

function AnalysisRecords({
  title,
  records,
  translate,
}: {
  title: string;
  records: EvidenceAnalysisRecord[];
  translate: (value: string) => string;
}): JSX.Element | null {
  if (!records.length) return null;
  return <section className="min-w-0 rounded-lg border border-raven-border p-3">
    <h3 className="text-sm font-semibold">{translate(title)} <span className="font-normal text-raven-muted">({records.length})</span></h3>
    <ul className="mt-2 space-y-2">{records.slice(0, 12).map((record, index) => {
      const titleText = textValue(record.title ?? record.candidate ?? record.kind ?? record.name) || translate("Evidence record");
      const summary = textValue(record.summary ?? record.reason ?? record.candidate ?? record.detail);
      const destination = textValue(record.target_url);
      const safeDestination = destination.startsWith("/") && !destination.startsWith("//") ? destination : null;
      return <li key={`${textValue(record.id ?? record.evidence_id)}-${index}`} className="min-w-0 rounded bg-raven-panelSoft p-2 text-sm">
        <div className="flex flex-wrap items-center gap-2"><strong className="break-words">{safeDestination ? <Link to={safeDestination} className="text-raven-violet underline">{titleText}</Link> : titleText}</strong>{record.confidence ? <span className="rounded border border-raven-border px-1.5 py-0.5 text-[10px]">{translate(textValue(record.confidence))}</span> : null}</div>
        {summary ? <p className="mt-1 break-words text-xs leading-5 text-raven-muted">{summary}</p> : null}
        {record.observed_at ? <p className="mt-1 break-words text-[10px] text-raven-muted">{textValue(record.observed_at)} · {textValue(record.source)}</p> : null}
      </li>;
    })}</ul>
  </section>;
}

function textValue(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function historyLabel(item: EvidenceAnalysisListItem, translate: (value: string) => string): string {
  const name = workflows.find((workflowItem) => workflowItem.value === item.workflow)?.label ?? item.workflow;
  return `${translate(name)} · ${new Date(item.generated_at).toLocaleString()}`;
}

function safeInventory(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== "object") return undefined;
  const source = value as Record<string, unknown>;
  if (source.available !== true) return undefined;
  const processes = Array.isArray(source.processes) ? source.processes.slice(0, 100) : [];
  const services = Array.isArray(source.services) ? source.services.slice(0, 100) : [];
  return {
    available: true,
    detail: typeof source.detail === "string" ? source.detail.slice(0, 160) : "",
    processes: processes.filter(isRecord).map((item) => ({
      pid: numberValue(item.pid),
      name: stringValue(item.name, 160),
      cpuPercent: numberValue(item.cpuPercent),
      memoryBytes: numberValue(item.memoryBytes),
      startedAtUnix: numberValue(item.startedAtUnix),
      runtimeSeconds: numberValue(item.runtimeSeconds),
    })),
    services: services.filter(isRecord).map((item) => ({
      name: stringValue(item.name, 128),
      displayName: stringValue(item.displayName, 160),
      state: stringValue(item.state, 40),
      startType: typeof item.startType === "string" ? item.startType.slice(0, 40) : null,
      pid: typeof item.pid === "number" ? item.pid : null,
    })),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function stringValue(value: unknown, limit: number): string {
  return typeof value === "string" ? value.slice(0, limit) : "unknown";
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}
