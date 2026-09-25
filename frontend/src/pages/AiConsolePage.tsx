import {
  Archive,
  Bot,
  Copy,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { PageHeader } from "../components/PageHeader";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  archiveAiSession,
  auditAiPromptCopy,
  cancelAiGeneration,
  createAiPromptHandoff,
  createAiSession,
  deleteAiSession,
  getAiCatalog,
  getAiPreferences,
  getAiTools,
  getAiSession,
  listAiSessions,
  previewAiKnowledgeContext,
  refreshAiCatalog,
  renameAiSession,
  sendAiMessageStream,
  testAiModel,
  updateAiPreferences,
  getAccessToken,
  type AiWorkflow,
} from "../lib/api";
import type {
  AiExecutionMode,
  AiKnowledgePolicy,
  AiModel,
  AiPromptHandoffResponse,
  AiSessionView,
} from "../types";
import { resolveAiEvidenceDestination } from "../lib/aiEvidence.js";
import { useAuth } from "../lib/useAuth";
import { useI18n } from "../lib/i18n";

const executionModes: AiExecutionMode[] = ["free_only", "local_only", "any_configured"];
const knowledgePolicies: AiKnowledgePolicy[] = ["verified_only", "trusted_plus", "all_allowed"];

export function AiConsolePage(): JSX.Element {
  const { t } = useI18n();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [contextPolicy, setContextPolicy] = useState<AiKnowledgePolicy>("verified_only");
  const [contextPreviewOpen, setContextPreviewOpen] = useState(false);
  const [selectedCitationIds, setSelectedCitationIds] = useState<string[]>([]);
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [handoffKind, setHandoffKind] = useState<"recommendation" | "asset" | "investigation">("investigation");
  const [handoffTitle, setHandoffTitle] = useState("");
  const [handoffSummary, setHandoffSummary] = useState("");
  const [toast, setToast] = useState<ToastState | null>(null);
  const [modelFilter, setModelFilter] = useState<"all" | "free" | "local" | "remote" | "tools" | "reasoning">("all");
  const [handoffResult, setHandoffResult] = useState<AiPromptHandoffResponse | null>(null);
  const [workflow, setWorkflow] = useState<AiWorkflow | undefined>();
  const [workflowScopeId, setWorkflowScopeId] = useState("");
  const [allowRemoteToolContext, setAllowRemoteToolContext] = useState(false);

  const catalog = useQuery({
    queryKey: ["ai-catalog"],
    queryFn: getAiCatalog,
    staleTime: 30_000,
    retry: 1,
  });
  const preferences = useQuery({
    queryKey: ["ai-preferences"],
    queryFn: getAiPreferences,
    staleTime: 30_000,
    retry: 1,
  });
  const sessions = useQuery({
    queryKey: ["ai-sessions"],
    queryFn: listAiSessions,
    staleTime: 10_000,
    retry: 1,
  });
  const toolCatalog = useQuery({
    queryKey: ["ai-tools"],
    queryFn: getAiTools,
    staleTime: 60_000,
    retry: 1,
  });
  const desktopInventory = useQuery({
    queryKey: ["ai-desktop-inventory"],
    queryFn: async () => {
      const core = nativeCore();
      const token = getAccessToken();
      if (!core || !token) return null;
      return core.invoke("get_local_host_inventory", { token });
    },
    enabled: Boolean(isAdmin && hasNativeCore()),
    staleTime: 10_000,
    refetchInterval: 15_000,
    retry: false,
  });
  const activeSession = useQuery({
    queryKey: ["ai-session", activeId],
    queryFn: () => getAiSession(activeId as string),
    enabled: Boolean(activeId),
    refetchInterval: (query) => query.state.data?.status === "running" ? 1500 : false,
    retry: 1,
  });

  const models = catalog.data?.models ?? [];
  const mode = preferences.data?.execution_mode ?? "free_only";
  const recommendedModel = catalog.data?.recommended_model_id
    ? models.find((model) => model.id === catalog.data?.recommended_model_id && model.available)
    : undefined;
  const selectedModelId = preferences.data?.selected_model_id
    ?? (mode === "local_only" && recommendedModel && !recommendedModel.local ? "" : recommendedModel?.id ?? "");
  const selectedModel = useMemo(
    () => models.find((model) => model.id === selectedModelId) ?? null,
    [models, selectedModelId],
  );
  const visibleModels = models.filter((model) => {
    if (modelFilter === "free") return model.free_status === "provider_reported_free";
    if (modelFilter === "local") return model.local;
    if (modelFilter === "remote") return model.remote;
    if (modelFilter === "tools") return model.supports_tools === true;
    if (modelFilter === "reasoning") return model.supports_reasoning === true;
    return true;
  });
  const session = activeSession.data;
  const sessionModel = session
    ? models.find((model) => model.id === `${session.provider_id}/${session.model_id}`) ?? null
    : null;
  const remoteToolContextAvailable = Boolean(
    sessionModel?.remote
      && !sessionModel.local
      && (workflow || sessionModel.supports_tools === true),
  );
  const requiresRemoteToolConsent = Boolean(
    sessionModel?.remote
      && !sessionModel.local
      && workflow,
  );

  const refreshMutation = useMutation({
    mutationFn: refreshAiCatalog,
    onSuccess: (value) => queryClient.setQueryData(["ai-catalog"], value),
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const preferenceMutation = useMutation({
    mutationFn: updateAiPreferences,
    onSuccess: (value) => {
      queryClient.setQueryData(["ai-preferences"], value);
      setToast({ kind: "success", message: t("AI preferences saved") });
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const createMutation = useMutation({
    mutationFn: () => {
      if (!selectedModelId) throw new Error(t("Select an available model first"));
      return createAiSession(selectedModelId, t("New AI chat"), contextPolicy);
    },
    onSuccess: async (created) => {
      setActiveId(created.id);
      setDraft("");
      setSelectedCitationIds([]);
      await queryClient.invalidateQueries({ queryKey: ["ai-sessions"] });
      await queryClient.invalidateQueries({ queryKey: ["ai-session", created.id] });
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const sendMutation = useMutation({
    mutationFn: () => {
      if (!activeId) throw new Error(t("Start a new chat before sending a message"));
      if (["analyze_asset", "explain_alert", "analyze_investigation"].includes(workflow ?? "") && !isUuid(workflowScopeId)) {
        throw new Error(t("Enter a valid selected record ID for this workflow"));
      }
      if (requiresRemoteToolConsent && !allowRemoteToolContext) {
        throw new Error(t("Approve the remote evidence preview before sending this turn"));
      }
      setStreamingText("");
      return sendAiMessageStream(activeId, draft, selectedCitationIds, contextPolicy, (delta) => setStreamingText((current) => current + delta), {
        workflow,
        workflowScopeId: workflowScopeId || undefined,
        desktopInventory: desktopInventory.data ?? undefined,
        allowRemoteToolContext,
      });
    },
    onSuccess: async () => {
      setDraft("");
      setStreamingText("");
      setWorkflow(undefined);
      setAllowRemoteToolContext(false);
      await queryClient.invalidateQueries({ queryKey: ["ai-session", activeId] });
      await queryClient.invalidateQueries({ queryKey: ["ai-sessions"] });
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
      void queryClient.invalidateQueries({ queryKey: ["ai-session", activeId] });
    },
  });
  const cancelMutation = useMutation({
    mutationFn: () => activeId ? cancelAiGeneration(activeId) : Promise.resolve({ cancelled: false }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["ai-session", activeId] }),
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const previewMutation = useMutation({
    mutationFn: () => previewAiKnowledgeContext(draft, contextPolicy),
    onSuccess: (value) => {
      setContextPreviewOpen(true);
      setSelectedCitationIds(value.items.map((item) => item.citation_id));
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const testMutation = useMutation({
    mutationFn: () => testAiModel(selectedModelId),
    onSuccess: (value) => setToast({ kind: value.available ? "success" : "error", message: value.available ? `${value.response} · ${value.latency_ms} ms` : value.error ?? t("Model test failed") }),
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const handoffMutation = useMutation({
    mutationFn: () => createAiPromptHandoff(
      handoffKind,
      handoffTitle || t("Selected RavenTech analysis"),
      handoffSummary,
      selectedCitationIds,
      selectedModelId || undefined,
    ),
    onSuccess: async (value) => {
      setHandoffResult(value);
      try {
        await navigator.clipboard.writeText(value.prompt);
        await auditAiPromptCopy(value.content_hash, "prompt");
        setToast({ kind: "success", message: t("OpenCode prompt copied") });
      } catch {
        setToast({ kind: "error", message: t("Clipboard access is unavailable") });
      }
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameAiSession(id, title),
    onSuccess: async (value) => {
      if (value.id === activeId) await queryClient.invalidateQueries({ queryKey: ["ai-session", activeId] });
      await queryClient.invalidateQueries({ queryKey: ["ai-sessions"] });
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const sessionActionMutation = useMutation({
    mutationFn: async (action: { id: string; type: "archive" | "delete" }) => {
      if (action.type === "archive") return archiveAiSession(action.id);
      await deleteAiSession(action.id);
      return null;
    },
    onSuccess: async (_result, action) => {
      if (action.id === activeId) setActiveId(null);
      await queryClient.invalidateQueries({ queryKey: ["ai-sessions"] });
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });

  if (catalog.isLoading || preferences.isLoading || sessions.isLoading) {
    return <LoadingBlock label={t("Loading AI workspace")} />;
  }
  if (catalog.isError || preferences.isError || sessions.isError) {
    return <ErrorBlock message={t("AI workspace could not be loaded")} />;
  }

  const canUseModel = (model: AiModel): boolean => {
    if (!model.available) return false;
    if (mode === "local_only") return model.local;
    if (mode === "free_only") return model.local || model.free_status === "provider_reported_free";
    return true;
  };
  const updateSelectedModel = (modelId: string): void => {
    preferenceMutation.mutate({ ...preferences.data!, selected_model_id: modelId || null });
  };
  const updatePreferredModel = (kind: "preferred_local_model_id" | "preferred_free_model_id", modelId: string): void => {
    preferenceMutation.mutate({ ...preferences.data!, [kind]: modelId || null });
  };
  const updateMode = (nextMode: AiExecutionMode): void => {
    const current = models.find((model) => model.id === selectedModelId);
    const remainsAllowed = current && (
      nextMode === "any_configured"
      || (nextMode === "local_only" && current.local)
      || (nextMode === "free_only" && (current.local || current.free_status === "provider_reported_free"))
    );
    preferenceMutation.mutate({
      ...preferences.data!,
      execution_mode: nextMode,
      selected_model_id: remainsAllowed ? selectedModelId : null,
    });
  };
  const chooseActiveSession = (item: AiSessionView): void => {
    setStreamingText("");
    setActiveId(item.id);
    setContextPolicy(item.context_policy);
    setSelectedCitationIds([]);
  };
  const prepareWorkflow = (kind: AiWorkflow): void => {
    setWorkflow(kind);
    setAllowRemoteToolContext(false);
    const prompt = {
      analyze_server: "Analyze the primary RavenTech server using current evidence. Separate facts, interpretations, hypotheses, and manual recommendations.",
      analyze_resource_usage: "Analyze current host resource usage using bounded metrics, top processes, recent timeline evidence, and verified Knowledge where relevant.",
      analyze_services: "Analyze existing local service inventory, deterministic posture, recent changes, and relevant Knowledge. Do not change service state.",
      analyze_ports: "Review existing local listening port observations and relevant policy evidence. An open port alone is not a vulnerability.",
      analyze_lan: "Analyze the existing authorized LAN inventory. Do not initiate discovery or service checks.",
      analyze_asset: "Analyze the selected LAN asset from stored observations and endpoint telemetry.",
      explain_posture: "Explain the current deterministic RavenTech Security Posture and its evidence.",
      explain_alert: "Explain the selected alert and identify the evidence and uncertainty.",
      analyze_investigation: "Summarize the selected investigation using accessible findings and timeline evidence.",
    } satisfies Record<AiWorkflow, string>;
    setDraft(prompt[kind]);
  };
  const toggleCitation = (citationId: string): void => {
    setSelectedCitationIds((selected) => selected.includes(citationId)
      ? selected.filter((item) => item !== citationId)
      : selected.length < 5 ? [...selected, citationId] : selected);
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("RavenTech AI")}
        eyebrow={t("AI Operations")}
        actions={(
          <button type="button" onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending} className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:bg-raven-panelSoft disabled:opacity-50">
            <RefreshCw size={15} className={refreshMutation.isPending ? "animate-spin" : ""} />{t("Refresh models")}
          </button>
        )}
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <p className="-mt-4 mb-4 text-sm text-raven-muted">{t("Chat and evidence-aware analysis using explicitly selected local Knowledge context.")}</p>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-4">
          <div className="rounded-xl border border-raven-border bg-raven-panel p-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex min-w-52 flex-1 flex-col gap-1">
                <label htmlFor="ai-model" className="text-xs font-semibold uppercase tracking-wide text-raven-muted">{t("Model")}</label>
                <select aria-label={t("Filter models")} value={modelFilter} onChange={(event) => setModelFilter(event.target.value as typeof modelFilter)} className="rounded-md border border-raven-border bg-raven-bg px-2 py-1 text-xs text-raven-text">
                  {([["all", "All"], ["free", "Free"], ["local", "Local"], ["remote", "Remote"], ["tools", "Tool capable"], ["reasoning", "Reasoning"]] as const).map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}
                </select>
                <select id="ai-model" value={selectedModelId} onChange={(event) => updateSelectedModel(event.target.value)} className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text">
                  <option value="">{t("No model selected")}</option>
                  {visibleModels.map((model) => (
                    <option key={model.id} value={model.id} disabled={!canUseModel(model)}>
                      {model.display_name} · {model.provider_id} · {model.local ? t("Local") : t("Remote")} · {freeLabel(model, t)}{model.available ? "" : ` · ${t("Unavailable")}`}
                    </option>
                  ))}
                </select>
              </div>
              {selectedModelId && !selectedModel?.available ? <p role="status" className="w-full text-sm text-amber-300">{t("Model unavailable. Your saved sessions are preserved; refresh models or select another model.")}</p> : null}
              {selectedModel ? <p className="w-full text-xs text-raven-muted">{t("Changing the model applies to a new session. Existing sessions keep their recorded provider and model.")}</p> : null}
              <div className="min-w-36 flex-1">
                <label htmlFor="ai-mode" className="text-xs font-semibold uppercase tracking-wide text-raven-muted">{t("Privacy mode")}</label>
                <select id="ai-mode" value={mode} onChange={(event) => updateMode(event.target.value as AiExecutionMode)} className="mt-1 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm">
                  {executionModes.map((value) => <option key={value} value={value}>{modeLabel(value, t)}</option>)}
                </select>
              </div>
              {isAdmin ? <button type="button" disabled={!selectedModelId || testMutation.isPending} onClick={() => testMutation.mutate()} className="rounded-md border border-raven-border px-3 py-2 text-sm disabled:opacity-50">{testMutation.isPending ? t("Testing") : t("Test model")}</button> : null}
              <div className="flex items-center gap-2 rounded-full border border-raven-border px-3 py-2 text-xs">
                <span className={`h-2 w-2 rounded-full ${catalog.data?.runtime.available ? "bg-emerald-400" : "bg-slate-400"}`} />
                <span>{catalog.data?.runtime.available ? t("OpenCode available") : t("OpenCode optional")}</span>
                {catalog.data?.runtime.version ? <span className="text-raven-muted">{catalog.data.runtime.version}</span> : null}
              </div>
            </div>
            {catalog.data?.warning ? <p className="mt-3 text-sm text-raven-muted">{t(catalog.data.warning)}</p> : null}
            {selectedModel ? <p className="mt-3 flex items-center gap-2 text-sm text-raven-muted"><span className="rounded bg-raven-panelSoft px-2 py-1 font-semibold text-raven-text">{selectedModel.local ? t("LOCAL") : t("REMOTE")}</span><span>{freeLabel(selectedModel, t)}</span><span>· {selectedModel.provider_id}/{selectedModel.model_id}</span></p> : null}
          </div>

          <div className="grid min-h-[520px] gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
            <aside className="rounded-xl border border-raven-border bg-raven-panel p-3">
              <button type="button" onClick={() => createMutation.mutate()} disabled={!selectedModel || !canUseModel(selectedModel) || createMutation.isPending} className="flex w-full items-center justify-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"><Plus size={16} />{t("New chat")}</button>
              <p className="mb-2 mt-5 px-1 text-xs font-semibold uppercase tracking-wide text-raven-muted">{t("Recent sessions")}</p>
              <div className="space-y-1">
                {(sessions.data ?? []).map((item) => (
                  <div key={item.id} className={`group flex items-center gap-1 rounded-md ${item.id === activeId ? "bg-raven-panelSoft" : "hover:bg-raven-panelSoft"}`}>
                    <button type="button" onClick={() => chooseActiveSession(item)} className="min-w-0 flex-1 px-2 py-2 text-left text-sm">
                      <span className="block truncate">{item.title}</span>
                      <span className="block truncate text-xs text-raven-muted">{item.provider_id}/{item.model_id}</span>
                    </button>
                    <button type="button" title={t("Rename session")} aria-label={t("Rename session")} onClick={() => { const title = window.prompt(t("Rename session"), item.title); if (title?.trim()) renameMutation.mutate({ id: item.id, title: title.trim() }); }} className="p-1 text-raven-muted hover:text-raven-text"><Pencil size={14} /></button>
                    <button type="button" title={t("Archive session")} aria-label={t("Archive session")} onClick={() => sessionActionMutation.mutate({ id: item.id, type: "archive" })} className="p-1 text-raven-muted hover:text-raven-text"><Archive size={14} /></button>
                    <button type="button" title={t("Delete session")} aria-label={t("Delete session")} onClick={() => sessionActionMutation.mutate({ id: item.id, type: "delete" })} className="mr-1 p-1 text-raven-muted hover:text-red-400"><Trash2 size={14} /></button>
                  </div>
                ))}
                {!sessions.data?.length ? <p className="px-2 py-3 text-xs text-raven-muted">{t("No saved sessions yet")}</p> : null}
              </div>
            </aside>

            <div className="flex min-h-[520px] flex-col rounded-xl border border-raven-border bg-raven-panel">
              {session ? (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-raven-border p-4">
                    <div><h2 className="font-semibold">{session.title}</h2><p className="mt-1 text-xs text-raven-muted">{sessionModel?.local ? t("Local execution") : t("Remote execution")}{sessionModel ? ` · ${session.provider_id}/${session.model_id}` : ` · ${session.provider_id}/${session.model_id}`}</p></div>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setHandoffOpen((value) => !value)} className="inline-flex items-center gap-1 rounded-md border border-raven-border px-2 py-1.5 text-xs"><Copy size={13} />{t("Prompt handoff")}</button>
                      {session.status === "running" ? <button type="button" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending} className="inline-flex items-center gap-1 rounded-md border border-raven-border px-2 py-1.5 text-xs"><Square size={12} />{t("Cancel")}</button> : null}
                    </div>
                  </div>
                  <div className="border-b border-raven-border px-4 py-3">
                    <div className="flex flex-wrap gap-2" aria-label={t("Read-only analysis workflows")}>
                      {(["analyze_server", "analyze_resource_usage", "analyze_services", "analyze_ports", "analyze_lan", "analyze_asset", "explain_posture", "explain_alert", "analyze_investigation"] as const).map((kind) => <button key={kind} type="button" onClick={() => prepareWorkflow(kind)} disabled={session.status === "running"} className={`rounded border px-2 py-1.5 text-xs ${workflow === kind ? "border-raven-violet text-raven-violet" : "border-raven-border hover:bg-raven-panelSoft"}`}>
                        {t(({ analyze_server: "Analyze Server", analyze_resource_usage: "Analyze Resource Usage", analyze_services: "Analyze Services", analyze_ports: "Analyze Ports", analyze_lan: "Analyze LAN", analyze_asset: "Analyze Asset", explain_posture: "Explain Posture", explain_alert: "Explain Alert", analyze_investigation: "Analyze Investigation" })[kind])}
                      </button>)}
                    </div>
                    {workflow ? <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-raven-muted"><span>{t("Prepared context workflow")}: {workflow.replace(/_/g, " ")}</span>{["analyze_asset", "explain_alert", "analyze_investigation"].includes(workflow) ? <input value={workflowScopeId} onChange={(event) => { setWorkflowScopeId(event.target.value); setAllowRemoteToolContext(false); }} aria-label={t("Selected asset, alert, or investigation ID")} placeholder={t("Selected record ID")} className="min-w-56 flex-1 rounded border border-raven-border bg-raven-bg px-2 py-1.5" /> : null}<button type="button" onClick={() => { setWorkflow(undefined); setAllowRemoteToolContext(false); }} className="rounded border border-raven-border px-2 py-1">{t("Clear")}</button></div> : null}
                    <p className="mt-2 text-[11px] text-raven-muted">{t("Only fixed read-only RavenTech tools are available. No shell, SQL, filesystem, scanning, or write actions.")}</p>
                  </div>
                  <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
                    {(session.messages ?? []).map((message) => (
                      <article key={message.id} className={`max-w-[92%] rounded-xl p-3 ${message.role === "user" ? "ml-auto bg-raven-violet/20" : "bg-raven-panelSoft"}`}>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-raven-muted">{message.role === "assistant" ? `${t("AI-generated analysis")} · ${message.provider_id}/${message.model_id}` : t("You")}</p>
                        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                        {message.role === "assistant" && message.citation_validation?.unverified_response_references.length ? <p className="mt-2 text-xs text-amber-300">{t("Unverified citation references")}: {message.citation_validation.unverified_response_references.join(", ")}</p> : null}
                        {message.supplied_citations.length ? <div className="mt-2 border-t border-raven-border pt-2 text-xs text-raven-muted"><span className="font-semibold">{t("Sources used")}: </span>{message.supplied_citations.join(", ")}</div> : null}
                        {message.context_sources.some((item) => item.kind === "tool_activity") ? <ToolEvidencePanel sources={message.context_sources.filter((item) => item.kind === "tool_activity")} translate={t} /> : null}
                      </article>
                    ))}
                    {streamingText ? <article className="max-w-[92%] rounded-xl bg-raven-panelSoft p-3" aria-live="polite"><p className="mb-1 text-xs font-semibold uppercase tracking-wide text-raven-muted">{t("AI-generated analysis")} · {session.provider_id}/{session.model_id}</p><p className="whitespace-pre-wrap text-sm leading-6">{streamingText}</p></article> : null}
                    {session.status === "running" ? <div className="flex items-center gap-2 text-sm text-raven-muted"><Sparkles size={15} className="animate-pulse" />{t("Generating response")}</div> : null}
                    {session.status === "failed" ? <p role="status" className="text-sm text-amber-300">{t("The provider request failed. Your session is preserved and RavenTech core services remain available.")}</p> : null}
                  </div>
                  <div className="border-t border-raven-border p-4">
                    {remoteToolContextAvailable ? <div className="mb-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-xs">
                      <label className="flex items-start gap-2 font-medium"><input type="checkbox" checked={allowRemoteToolContext} onChange={(event) => setAllowRemoteToolContext(event.target.checked)} /><span>{t("Allow this remote model to receive read-only RavenTech evidence for this turn")}</span></label>
                      <p className="mt-2 text-raven-muted">{t("Preview: host metrics, process and service summaries, listener observations, authorized LAN metadata, deterministic posture, alerts, timeline entries, and only the Knowledge excerpts selected below. No commands, credentials, raw banners, or write actions are shared.")}</p>
                    </div> : null}
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={contextPreviewOpen} onChange={(event) => { setContextPreviewOpen(event.target.checked); if (!event.target.checked) setSelectedCitationIds([]); }} />{t("Use Knowledge context")}</label>
                      {contextPreviewOpen ? <div className="flex items-center gap-2"><select value={contextPolicy} onChange={(event) => { setContextPolicy(event.target.value as AiKnowledgePolicy); setSelectedCitationIds([]); }} className="rounded border border-raven-border bg-raven-bg px-2 py-1 text-xs">{knowledgePolicies.map((policy) => <option key={policy} value={policy}>{knowledgePolicyLabel(policy, t)}</option>)}</select><button type="button" onClick={() => previewMutation.mutate()} disabled={!draft.trim() || previewMutation.isPending} className="rounded border border-raven-border px-2 py-1 text-xs disabled:opacity-50">{previewMutation.isPending ? t("Preparing preview") : t("Preview sources")}</button></div> : null}
                    </div>
                    {contextPreviewOpen && previewMutation.data ? <div className="mb-3 max-h-44 space-y-2 overflow-y-auto rounded-lg border border-raven-border p-2">
                      {previewMutation.data.items.map((item) => <label key={item.citation_id} className="flex cursor-pointer gap-2 rounded p-2 hover:bg-raven-panelSoft"><input type="checkbox" checked={selectedCitationIds.includes(item.citation_id)} onChange={() => toggleCitation(item.citation_id)} /><span className="min-w-0"><span className="block text-xs font-semibold">{item.title} · {item.trust_level}/{item.verification_status}</span><span className="line-clamp-3 block text-xs text-raven-muted">{item.excerpt}</span><span className="mt-1 block text-[10px] text-raven-muted">{item.citation_id}</span></span></label>)}
                      {!previewMutation.data.items.length ? <p className="p-2 text-xs text-raven-muted">{t("No matching Knowledge excerpts")}</p> : null}
                    </div> : null}
                    <div className="flex items-end gap-2">
                      <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); if (draft.trim() && session.status !== "running") sendMutation.mutate(); } }} rows={3} maxLength={12_000} placeholder={t("Ask a question or request analysis...")} className="min-h-20 flex-1 resize-y rounded-lg border border-raven-border bg-raven-bg px-3 py-2 text-sm outline-none focus:border-raven-violet" disabled={session.status === "running"} />
                      <button type="button" onClick={() => sendMutation.mutate()} disabled={!draft.trim() || session.status === "running" || sendMutation.isPending} className="inline-flex items-center gap-2 rounded-lg bg-raven-violet px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><Send size={15} />{t("Send")}</button>
                    </div>
                    <p className="mt-2 text-xs text-raven-muted">{t("AI-generated analysis is separate from verified RavenTech evidence. Selected Knowledge excerpts are shared with the selected model; remote operational evidence requires turn-specific approval.")}</p>
                  </div>
                </>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
                  <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-raven-violet/15 text-raven-violet"><Bot size={27} /></div>
                  <h2 className="text-lg font-semibold">{t("Start an evidence-aware AI session")}</h2>
                  <p className="mt-2 max-w-lg text-sm text-raven-muted">{catalog.data?.runtime.available ? t("Choose an available model and start a chat. The model receives only the message and context you explicitly select.") : catalog.data?.runtime.message}</p>
                  {!models.some((model) => model.available) ? <div className="mt-5 max-w-lg rounded-lg border border-raven-border bg-raven-panelSoft p-4 text-left text-sm"><p className="flex items-center gap-2 font-semibold"><ShieldCheck size={16} />{t("AI is optional")}</p><p className="mt-2 text-raven-muted">{t("Configure a provider in OpenCode or start a local Ollama or LM Studio model. RavenTech core monitoring and investigations continue to work without AI.")}</p><p className="mt-2 text-xs text-raven-muted">{catalog.data?.runtime.message}</p></div> : null}
                  <button type="button" onClick={() => createMutation.mutate()} disabled={!selectedModel || !canUseModel(selectedModel)} className="mt-5 rounded-md bg-raven-violet px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{t("New chat")}</button>
                </div>
              )}
            </div>
          </div>
        </div>

        <aside className="space-y-4">
          <section className="rounded-xl border border-raven-border bg-raven-panel p-4">
            <h2 className="font-semibold">{t("Model and privacy")}</h2>
            <div className="mt-3 space-y-3 text-sm">
              <StatusLine label={t("OpenCode")} value={catalog.data?.runtime.available ? t("Available") : catalog.data?.runtime.status === "server_stopped" ? t("Server stopped") : t("Optional / not connected")} />
              <StatusLine label={t("Available models")} value={String(models.filter((model) => model.available).length)} />
              <StatusLine label={t("Local providers")} value={String(catalog.data?.providers.filter((provider) => provider.local && provider.connected).length ?? 0)} />
              <StatusLine label={t("Remote providers")} value={String(catalog.data?.providers.filter((provider) => provider.remote && provider.connected).length ?? 0)} />
              <StatusLine label={t("Execution policy")} value={modeLabel(mode, t)} />
              <StatusLine label={t("Read-only tools")} value={`${toolCatalog.data?.read_only_count ?? 0} · ${t("writes disabled")}`} />
            </div>
            {session?.tool_activity?.length ? <div className="mt-4 border-t border-raven-border pt-3"><h3 className="text-sm font-semibold">{t("Tool activity")}</h3><ul className="mt-2 max-h-48 space-y-2 overflow-y-auto text-xs">{session.tool_activity.map((activity, index) => <li key={`${activity.timestamp}-${index}`} className="rounded border border-raven-border p-2"><span className="font-medium">{activity.tool_id}</span><span className="ml-2 text-raven-muted">{t(activity.outcome)} · {activity.duration_ms ?? "—"} ms</span>{activity.safe_error_code ? <span className="ml-2 text-amber-300">{activity.safe_error_code}</span> : null}</li>)}</ul></div> : null}
            <div className="mt-3 text-xs text-raven-muted">{t("Desktop inventory")}: {desktopInventory.data ? t("available") : t("not supplied")}</div>
            <div className="mt-4 space-y-2 border-t border-raven-border pt-3">
              <label className="block text-xs text-raven-muted">{t("Preferred local model")}
                <select value={preferences.data?.preferred_local_model_id ?? ""} onChange={(event) => updatePreferredModel("preferred_local_model_id", event.target.value)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-2 py-1 text-sm">
                  <option value="">{t("No preference")}</option>{models.filter((model) => model.local).map((model) => <option key={model.id} value={model.id}>{model.display_name} · {model.provider_id}</option>)}
                </select>
              </label>
              <label className="block text-xs text-raven-muted">{t("Preferred free model")}
                <select value={preferences.data?.preferred_free_model_id ?? ""} onChange={(event) => updatePreferredModel("preferred_free_model_id", event.target.value)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-2 py-1 text-sm">
                  <option value="">{t("No preference")}</option>{models.filter((model) => model.free_status === "provider_reported_free").map((model) => <option key={model.id} value={model.id}>{model.display_name} · {model.provider_id}</option>)}
                </select>
              </label>
            </div>
            {isAdmin ? <p className="mt-3 text-xs text-raven-muted">{t("Model tests send only a harmless READY prompt and are limited to local or provider-reported free models.")}</p> : null}
          </section>
          <section className="rounded-xl border border-raven-border bg-raven-panel p-4">
            <h2 className="font-semibold">{t("Data destination")}</h2>
            <p className="mt-2 text-sm text-raven-muted">{selectedModel?.local ? t("Execution stays with the detected local provider endpoint.") : selectedModel ? t("This model is remote. The selected provider receives the message and any explicitly selected context.") : t("Choose a model to review its local or remote execution label.")}</p>
            <p className="mt-3 text-xs text-raven-muted">{t("Provider authentication remains in OpenCode. RavenTech does not store provider keys.")}</p>
          </section>
          {handoffOpen ? <section className="rounded-xl border border-raven-border bg-raven-panel p-4">
            <h2 className="font-semibold">{t("Copy prompt to OpenCode")}</h2>
            <label className="mt-3 block text-xs text-raven-muted">{t("Analysis type")}</label>
            <select value={handoffKind} onChange={(event) => setHandoffKind(event.target.value as typeof handoffKind)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg p-2 text-sm"><option value="recommendation">{t("Security Posture recommendation")}</option><option value="asset">{t("LAN asset")}</option><option value="investigation">{t("Investigation")}</option></select>
            <input value={handoffTitle} onChange={(event) => setHandoffTitle(event.target.value)} placeholder={t("Subject") } className="mt-2 w-full rounded border border-raven-border bg-raven-bg p-2 text-sm" />
            <textarea value={handoffSummary} onChange={(event) => setHandoffSummary(event.target.value)} rows={4} maxLength={4000} placeholder={t("Add only the facts you want in the copied prompt") } className="mt-2 w-full rounded border border-raven-border bg-raven-bg p-2 text-sm" />
            <button type="button" onClick={() => handoffMutation.mutate()} disabled={handoffMutation.isPending} className="mt-2 inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm"><Copy size={14} />{t("Copy OpenCode prompt")}</button>
            {handoffResult?.command ? <button type="button" onClick={async () => { try { await navigator.clipboard.writeText(handoffResult.command!); await auditAiPromptCopy(handoffResult.content_hash, "command"); setToast({ kind: "success", message: t("OpenCode command copied. RavenTech did not execute it.") }); } catch { setToast({ kind: "error", message: t("Clipboard access is unavailable") }); } }} className="ml-2 mt-2 inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm"><Copy size={14} />{t("Copy OpenCode command")}</button> : null}
            {handoffResult ? <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-raven-panelSoft p-2 text-xs text-raven-muted">{handoffResult.prompt}</pre> : null}
            <p className="mt-2 text-xs text-raven-muted">{t("The copied prompt contains only the facts entered here and selected source references. It is not executed by RavenTech.")}</p>
          </section> : null}
        </aside>
      </section>
      {activeSession.isLoading && activeId ? <LoadingBlock label={t("Loading saved session")} /> : null}
      {sessions.data?.length === 0 ? <EmptyBlock title={t("No saved sessions yet")} message={t("Start a new chat after selecting an available model.")} /> : null}
    </div>
  );
}

function StatusLine({ label, value }: { label: string; value: string }): JSX.Element {
  return <div className="flex items-center justify-between gap-3"><span className="text-raven-muted">{label}</span><span className="text-right font-medium">{value}</span></div>;
}

function freeLabel(model: AiModel, translate: (value: string) => string): string {
  if (model.local) return translate("Local");
  if (model.free_status === "provider_reported_free") return translate("Free · provider reported");
  if (model.free_status === "paid") return translate("Paid metadata");
  return translate("Cost unknown");
}

function modeLabel(mode: AiExecutionMode, translate: (value: string) => string): string {
  if (mode === "free_only") return translate("Free only");
  if (mode === "local_only") return translate("Local only");
  return translate("Any configured");
}

function knowledgePolicyLabel(policy: AiKnowledgePolicy, translate: (value: string) => string): string {
  if (policy === "verified_only") return translate("Verified only");
  if (policy === "trusted_plus") return translate("Trusted and reviewed");
  return translate("All enabled sources");
}

type NativeCore = { invoke: (command: string, args?: Record<string, unknown>) => Promise<unknown> };
function nativeCore(): NativeCore | null {
  try {
    const current = window as Window & { __TAURI__?: { core?: NativeCore } };
    const parent = window.parent !== window
      ? window.parent as Window & { __TAURI__?: { core?: NativeCore } }
      : undefined;
    return current.__TAURI__?.core ?? parent?.__TAURI__?.core ?? null;
  } catch {
    return null;
  }
}
function hasNativeCore(): boolean { return nativeCore() !== null; }
function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

type EvidenceReference = {
  id: string;
  source_type: string;
  timestamp: string | null;
  confidence: string;
  freshness: string;
  scope: Record<string, unknown>;
};

function ToolEvidencePanel({
  sources,
  translate,
}: {
  sources: Array<Record<string, unknown>>;
  translate: (value: string) => string;
}): JSX.Element {
  return (
    <div className="mt-2 rounded border border-raven-border p-2 text-xs" aria-label={translate("Evidence panel")}>
      <strong>{translate("Evidence and tool activity")}</strong>
      {sources.map((source, index) => {
        const references = Array.isArray(source.evidence_references)
          ? source.evidence_references.filter(isEvidenceReference).slice(0, 10)
          : [];
        const fallbackIds = Array.isArray(source.evidence_ids)
          ? source.evidence_ids.filter((value): value is string => typeof value === "string").slice(0, 10)
          : [];
        return (
          <div key={`${String(source.tool_id)}-${index}`} className="mt-2 border-t border-raven-border pt-2">
            <p className="text-raven-muted">
              {String(source.tool_id)} · {source.success ? translate("completed") : translate("unavailable")}
            </p>
            {references.length ? <ul className="mt-1 space-y-1">
              {references.map((reference) => {
                const destination = resolveAiEvidenceDestination(reference.id, reference.scope);
                return <li key={reference.id} className="break-words text-raven-muted">
                  {destination
                    ? <Link to={destination} title={translate("Open source page")} className="text-raven-violet underline">{reference.id}</Link>
                    : <span>{reference.id}</span>}
                  <span> · {reference.source_type} · {translate("Confidence")}: {translate(reference.confidence)} · {translate("Freshness")}: {translate(reference.freshness)}</span>
                  {reference.timestamp ? <span> · {translate("Timestamp")}: {reference.timestamp}</span> : null}
                </li>;
              })}
            </ul> : fallbackIds.length ? <p className="mt-1 break-words text-raven-muted">{fallbackIds.join(", ")}</p> : null}
          </div>
        );
      })}
    </div>
  );
}

function isEvidenceReference(value: unknown): value is EvidenceReference {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<EvidenceReference>;
  return typeof item.id === "string"
    && typeof item.source_type === "string"
    && (item.timestamp === null || typeof item.timestamp === "string")
    && typeof item.confidence === "string"
    && typeof item.freshness === "string"
    && Boolean(item.scope && typeof item.scope === "object");
}
