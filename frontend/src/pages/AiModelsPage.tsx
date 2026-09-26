import { Cpu, HardDrive, RefreshCw, ShieldCheck, Sparkles, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { PageHeader } from "../components/PageHeader";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  deleteAiBenchmark,
  getAiCatalog,
  getAiPreferences,
  getLocalAiStatus,
  listAiBenchmarks,
  runAiBenchmark,
  testAiModel,
  updateAiPreferences,
} from "../lib/api";
import { useAuth } from "../lib/useAuth";
import { useI18n } from "../lib/i18n";
import type { AiExecutionMode, AiRoutingMode, AiTaskProfile } from "../types";

const taskProfiles: Array<[AiTaskProfile, string]> = [
  ["fast_triage", "Fast triage"],
  ["general_analyst", "General analyst"],
  ["deep_analysis", "Deep analysis"],
  ["knowledge_rag", "Knowledge / RAG"],
  ["tool_calling", "Tool calling"],
  ["structured_reports", "Structured reports"],
  ["bilingual", "Spanish and English"],
  ["offline", "Offline"],
];

export function AiModelsPage(): JSX.Element {
  const { t } = useI18n();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<ToastState | null>(null);
  const benchmarkAbort = useRef<AbortController | null>(null);
  const status = useQuery({
    queryKey: ["local-ai-status"],
    queryFn: () => getLocalAiStatus(),
    staleTime: 10_000,
    retry: 1,
  });
  const preferences = useQuery({ queryKey: ["ai-preferences"], queryFn: getAiPreferences });
  const catalog = useQuery({ queryKey: ["ai-catalog"], queryFn: getAiCatalog });
  const benchmarks = useQuery({ queryKey: ["ai-benchmarks"], queryFn: listAiBenchmarks });

  const refreshMutation = useMutation({
    mutationFn: () => getLocalAiStatus(true),
    onSuccess: (value) => queryClient.setQueryData(["local-ai-status"], value),
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const preferencesMutation = useMutation({
    mutationFn: async (patch: Partial<import("../types").AiPreferences>) => {
      if (!preferences.data) throw new Error(t("AI preferences are unavailable"));
      return updateAiPreferences({
        ...preferences.data,
        ...patch,
      });
    },
    onSuccess: async (value) => {
      queryClient.setQueryData(["ai-preferences"], value);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ai-catalog"] }),
        queryClient.invalidateQueries({ queryKey: ["local-ai-status"] }),
      ]);
      setToast({ kind: "success", message: t(value.offline_ai_enabled ? "Offline AI enabled; remote inference is blocked" : "Offline AI disabled") });
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const benchmarkMutation = useMutation({
    mutationFn: async (modelId: string) => {
      const controller = new AbortController();
      benchmarkAbort.current = controller;
      try {
        return await runAiBenchmark(modelId, true, controller.signal);
      } finally {
        benchmarkAbort.current = null;
      }
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["ai-benchmarks"] });
      setToast({ kind: result.status === "completed" ? "success" : "error", message: t(result.status === "completed" ? "Synthetic benchmark completed" : "Benchmark did not complete") });
    },
    onError: async (error) => {
      await queryClient.invalidateQueries({ queryKey: ["ai-benchmarks"] });
      const cancelled = error instanceof DOMException && error.name === "AbortError";
      setToast({ kind: cancelled ? "success" : "error", message: t(cancelled ? "Benchmark cancellation requested" : error.message) });
    },
  });
  const modelTestMutation = useMutation({
    mutationFn: testAiModel,
    onSuccess: (result) => setToast({
      kind: result.available ? "success" : "error",
      message: result.available
        ? `${t("Local model test passed")}: ${result.latency_ms ?? "?"} ms · ${result.response ?? "READY"} · ${t("Streaming")}: ${t(result.streaming)} · ${t("Structured output")}: ${t(result.structured_output)}`
        : `${t("Local model test failed")}: ${result.error ?? ""}`,
    }),
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteAiBenchmark,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["ai-benchmarks"] }),
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });

  if (status.isLoading || preferences.isLoading || catalog.isLoading || benchmarks.isLoading) {
    return <LoadingBlock label={t("Loading local AI status")} />;
  }
  if (status.isError || preferences.isError || catalog.isError || benchmarks.isError || !status.data || !preferences.data) {
    return <ErrorBlock message={status.error ?? preferences.error ?? catalog.error ?? benchmarks.error ?? t("Local AI status is unavailable")} />;
  }
  const profile = status.data.hardware;
  const models = status.data.models;
  const localModels = models.filter((model) => model.local && model.available);
  const preferredLocalId = preferences.data.selected_model_id
    ?? preferences.data.preferred_local_model_id
    ?? status.data.recommended_model_id;
  const preferredLocalModel = localModels.find((model) => model.id === preferredLocalId);
  const availableLocalRuntime = status.data.runtimes.find(
    (runtime) => runtime.status === "available" || runtime.status === "no_models",
  );
  const updateExecutionMode = (mode: AiExecutionMode): void => {
    const selected = catalog.data?.models.find((model) => model.id === preferences.data?.selected_model_id);
    const allowed = !selected || mode === "any_configured"
      || ((mode === "local_first" || mode === "free_only") && (selected.local || selected.free_status === "provider_reported_free"))
      || (mode === "local_only" && selected.local);
    preferencesMutation.mutate({ execution_mode: mode, selected_model_id: allowed ? preferences.data.selected_model_id : null });
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("AI Models")}
        eyebrow={t("Local AI and hardware")}
        actions={(
          <>
            <Link to="/ai" className="rounded-md border border-raven-border px-3 py-2 text-sm hover:bg-raven-panelSoft">{t("AI Console")}</Link>
            <button type="button" onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending} className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm disabled:opacity-50">
              <RefreshCw size={15} className={refreshMutation.isPending ? "animate-spin" : ""} />{t("Refresh local runtimes")}
            </button>
          </>
        )}
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
        <article className="rounded-xl border border-raven-border bg-raven-panel p-4">
          <div className="flex items-center gap-2"><Cpu size={17} className="text-raven-cyan" /><h2 className="font-semibold">{t("Hardware readiness")}</h2></div>
          <p className="mt-2 text-lg font-semibold">{t(readinessLabel(profile.readiness))}</p>
          <p className="text-sm text-raven-muted">{t(profile.readiness_reason)}</p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2 text-sm">
            <Metric label={t("Operating system")} value={`${profile.os_name} ${profile.os_version ?? ""} · ${profile.architecture}`} />
            <Metric label={t("CPU")} value={`${profile.cpu_model ?? t("Unknown")} · ${profile.physical_cores ?? "?"} ${t("physical cores")} / ${profile.logical_cores ?? "?"} ${t("logical")}`} />
            <Metric label={t("System RAM")} value={`${formatBytes(profile.system_memory_total_bytes)} ${t("total")} · ${formatBytes(profile.system_memory_available_bytes)} ${t("available")}`} />
            <Metric label={t("Disk space")} value={`${formatBytes(profile.disk_free_bytes)} ${t("free")}`} />
          </dl>
          <div className="mt-4 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-raven-muted">{t("Detected GPUs")}</p>
            {profile.gpus.length ? profile.gpus.map((gpu) => (
              <div key={gpu.gpu_id} className="rounded-lg border border-raven-border p-3 text-sm">
                <p className="font-medium">{gpu.vendor ?? t("Unknown")} · {gpu.model ?? t("Model unknown")}</p>
                <p className="text-xs text-raven-muted">{t("VRAM")}: {formatBytes(gpu.vram_total_bytes)} · {t("Compute backend")}: {gpu.compute_backend ?? t("Unknown")}{gpu.driver_version ? ` · ${t("Driver")}: ${gpu.driver_version}` : ""}</p>
                <p className="mt-1 text-[11px] text-raven-muted">{t("Source")}: {gpu.metadata_source}</p>
              </div>
            )) : <EmptyBlock title={t("No GPU confirmed")} message={t("CPU inference remains available; GPU and VRAM details are reported only when detected safely.")} />}
          </div>
          <p className="mt-3 flex items-center gap-2 text-[11px] text-raven-muted"><HardDrive size={13} />{t("Hardware profile is stored locally with benchmark results. No serial numbers are collected.")}</p>
        </article>

        <article className="rounded-xl border border-raven-border bg-raven-panel p-4">
          <div className="flex items-center gap-2"><ShieldCheck size={17} className="text-raven-cyan" /><h2 className="font-semibold">{t("Privacy and routing")}</h2></div>
          <label className="mt-4 flex items-start gap-3 rounded-lg border border-raven-border p-3">
            <input type="checkbox" className="mt-1" checked={preferences.data.offline_ai_enabled} onChange={(event) => {
              const selected = catalog.data?.models.find((model) => model.id === preferences.data?.selected_model_id);
              preferencesMutation.mutate({ offline_ai_enabled: event.target.checked, selected_model_id: event.target.checked && selected && !selected.local ? null : preferences.data.selected_model_id });
            }} disabled={preferencesMutation.isPending} />
            <span><span className="block font-medium">{t("Offline AI Mode")}</span><span className="mt-1 block text-sm text-raven-muted">{t("When enabled, remote inference is blocked. If local AI is unavailable, RavenTech uses deterministic features without cloud fallback.")}</span></span>
          </label>
          <p className="mt-3 rounded-md bg-raven-panelSoft p-3 text-sm">{preferences.data.offline_ai_enabled ? t("Remote inference: Blocked") : t("Remote inference: Allowed only by the selected privacy mode")}</p>
          <p className="mt-2 text-sm text-raven-muted">{t("Local runtime")}: {availableLocalRuntime?.name ?? t("Unavailable")} · {t("Model")}: {preferredLocalModel?.display_name ?? t("No local model available")}</p>
          <p className="mt-3 text-xs text-raven-muted">{t("Local-first uses a selected or preferred local model before an allowed remote free model. No paid model is selected silently.")}</p>
          <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-raven-muted">{t("Execution preference")}
            <select value={preferences.data.execution_mode} onChange={(event) => updateExecutionMode(event.target.value as AiExecutionMode)} disabled={preferencesMutation.isPending} className="mt-1 w-full rounded border border-raven-border bg-raven-bg p-2 text-sm font-normal text-raven-text">
              <option value="local_first">{t("Local first")}</option><option value="free_only">{t("Free only")}</option><option value="local_only">{t("Local only")}</option><option value="any_configured">{t("Any configured provider")}</option>
            </select>
          </label>
          <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-raven-muted">{t("Routing mode")}
            <select value={preferences.data.routing_mode} onChange={(event) => preferencesMutation.mutate({ routing_mode: event.target.value as AiRoutingMode })} disabled={preferencesMutation.isPending} className="mt-1 w-full rounded border border-raven-border bg-raven-bg p-2 text-sm font-normal text-raven-text">
              <option value="manual">{t("Manual")}</option><option value="recommended">{t("Recommended")}</option><option value="automatic_local">{t("Automatic local only")}</option>
            </select>
          </label>
          <p className="mt-2 text-xs text-raven-muted">{t("Automatic local routing uses installed local models only. A failed route never falls back to a remote provider.")}</p>
          <div className="mt-3 space-y-2">
            {taskProfiles.map(([profileId, label]) => <label key={profileId} className="block text-xs text-raven-muted">{t(label)}
              <select value={preferences.data.task_model_routes[profileId] ?? ""} onChange={(event) => {
                const routes = { ...preferences.data.task_model_routes };
                if (event.target.value) routes[profileId] = event.target.value;
                else delete routes[profileId];
                preferencesMutation.mutate({ task_model_routes: routes });
              }} disabled={preferencesMutation.isPending || !localModels.length} className="mt-1 w-full rounded border border-raven-border bg-raven-bg p-2 text-sm text-raven-text">
                <option value="">{t("Automatic hardware recommendation")}</option>{localModels.map((model) => <option key={model.id} value={model.id}>{model.display_name} · {t(model.fit)}</option>)}
              </select>
            </label>)}
          </div>
          <p className="mt-2 text-xs text-raven-muted">{t("AI execution tools exposed to the model")}: 0 · {t("Human approval remains mandatory for every write action.")}</p>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-raven-muted">{t("Local runtimes")}</p>
          <div className="mt-2 space-y-2">
            {status.data.runtimes.map((runtime) => (
              <div key={runtime.id} className="rounded-lg border border-raven-border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium">{runtime.name}</p><span className="rounded bg-raven-panelSoft px-2 py-1 text-[11px]">{t(runtime.status)}</span></div>
                <p className="mt-1 break-all text-xs text-raven-muted">{runtime.endpoint} · {t(runtime.endpoint_classification === "network" ? "Network endpoint blocked" : "Loopback only")} · {runtime.version ?? t("Version unknown")}</p>
                <p className="mt-1 text-xs text-raven-muted">{t(runtime.message)} · {runtime.model_count} {t("models")}</p>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="rounded-xl border border-raven-border bg-raven-panel p-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-semibold">{t("Installed local models")}</h2><p className="mt-1 text-xs text-raven-muted">{t("Model metadata comes from runtime reports; unknown values stay unknown. Fit uses approximate weights-plus-overhead and may not include context cache.")}</p></div><span className="text-xs text-raven-muted">{models.length} {t("installed")}</span></div>
        {models.length ? <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {models.map((model) => (
            <article key={model.id} className="rounded-lg border border-raven-border p-3">
              <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-medium">{model.display_name}</h3><p className="mt-1 text-xs text-raven-muted">{model.provider_id} · {model.model_id}</p></div><span className="rounded bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-200">{t("LOCAL")}</span></div>
              <dl className="mt-3 grid grid-cols-2 gap-2 text-xs"><Metric label={t("Size")} value={formatBytes(model.size_bytes)} /><Metric label={t("Parameters")} value={model.parameter_count ? formatCount(model.parameter_count) : t("Unknown")} /><Metric label={t("Quantization")} value={model.quantization ?? t("Unknown")} /><Metric label={t("Context window")} value={model.context_window ? formatCount(model.context_window) : t("Unknown")} /><Metric label={t("Approximate memory requirement")} value={formatBytes(model.estimated_memory_bytes)} /></dl>
              <p className="mt-3 text-xs"><strong>{t(model.fit)}</strong> · {t(model.fit_reason)}</p>
              <p className="mt-2 text-[11px] text-raven-muted">{t("Capabilities")}: {Object.entries(model.capabilities).map(([name, value]) => `${name}: ${t(value)}`).join(" · ") || t("Unknown")}</p>
              <p className="mt-1 text-[11px] text-raven-muted">{t("Metadata source")}: {model.metadata_source}</p>
              {isAdmin ? <div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => modelTestMutation.mutate(model.id)} disabled={modelTestMutation.isPending} className="rounded-md border border-raven-border px-3 py-1.5 text-xs disabled:opacity-50">{modelTestMutation.isPending ? t("Testing local model") : t("Test local model")}</button><button type="button" onClick={() => benchmarkMutation.mutate(model.id)} disabled={benchmarkMutation.isPending || model.fit === "insufficient_memory"} className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-1.5 text-xs disabled:opacity-50"><Sparkles size={13} />{benchmarkMutation.isPending ? t("Benchmark running") : t("Run synthetic benchmark")}</button></div> : null}
            </article>
          ))}
        </div> : <div className="mt-4"><EmptyBlock title={t("No installed local models found")} message={t("Install and start a supported local runtime, then refresh. RavenTech does not download model weights automatically.")} nextStep={t("Only already-installed models can be tested or benchmarked.")} /></div>}
        {benchmarkMutation.isPending ? <button type="button" onClick={() => benchmarkAbort.current?.abort()} className="mt-3 rounded-md border border-raven-border px-3 py-2 text-xs">{t("Cancel benchmark")}</button> : null}
      </section>

      <section className="rounded-xl border border-raven-border bg-raven-panel p-4">
        <h2 className="font-semibold">{t("Benchmark history")}</h2>
        <p className="mt-1 text-xs text-raven-muted">{t("Results are synthetic, hardware-specific, and approximate. Benchmark outputs and prompts are not retained.")}</p>
        {benchmarks.data?.length ? <div className="mt-3 space-y-2">{benchmarks.data.map((item) => (
          <article key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-raven-border p-3">
            <div className="min-w-0"><p className="font-medium">{item.model_id} · {t(item.status)}</p><p className="text-xs text-raven-muted">{new Date(item.started_at).toLocaleString()} · {t("Startup")}: {item.startup_latency_ms === null ? t("Unavailable") : `${item.startup_latency_ms} ms`} · {t("TTFT")}: {item.ttft_ms === null ? t("Unavailable") : `${item.ttft_ms} ms`} · {t("Throughput estimate")}: {item.tokens_per_second === null ? t("Unavailable") : `${item.tokens_per_second} tok/s`} · {t("Memory delta")}: {formatBytes(item.memory_delta_bytes)}</p><p className="mt-1 text-[11px] text-raven-muted">{Object.entries(item.scores).map(([key, score]) => `${t(key)}: ${score === null ? t("Unavailable") : `${score}%`}`).join(" · ")}</p></div>
            <button type="button" aria-label={t("Delete benchmark")} title={t("Delete benchmark")} onClick={() => deleteMutation.mutate(item.id)} disabled={deleteMutation.isPending} className="rounded p-2 text-raven-muted hover:text-red-300 disabled:opacity-50"><Trash2 size={14} /></button>
          </article>
        ))}</div> : <p className="mt-3 text-sm text-raven-muted">{t("No benchmark history")}</p>}
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return <div className="min-w-0"><dt className="text-[11px] uppercase tracking-wide text-raven-muted">{label}</dt><dd className="break-words text-sm text-raven-text">{value}</dd></div>;
}

function formatBytes(value: number | null): string {
  if (value === null || !Number.isFinite(value) || value < 0) return "Unknown";
  if (value === 0) return "0 B";
  const unit = Math.min(4, Math.floor(Math.log(value) / Math.log(1024)));
  return `${(value / 1024 ** unit).toFixed(unit > 0 ? 1 : 0)} ${["B", "KiB", "MiB", "GiB", "TiB"][unit]}`;
}

function formatCount(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);
}

function readinessLabel(value: string): string {
  return ({
    cpu_only_capable: "CPU-only capable",
    entry_local_ai: "Entry local AI",
    moderate_local_ai: "Moderate local AI capacity",
    high_local_ai: "High local AI capacity",
  } as Record<string, string>)[value] ?? "Unknown";
}
