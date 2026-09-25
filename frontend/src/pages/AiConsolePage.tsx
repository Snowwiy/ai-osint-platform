import {
  Archive,
  Bot,
  Check,
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
  getAiSession,
  listAiSessions,
  previewAiKnowledgeContext,
  refreshAiCatalog,
  renameAiSession,
  sendAiMessage,
  sendAiMessageStream,
  testAiModel,
  updateAiPreferences,
} from "../lib/api";
import type {
  AiExecutionMode,
  AiKnowledgePolicy,
  AiModel,
  AiPromptHandoffResponse,
  AiSessionView,
} from "../types";
import { useAuth } from "../lib/useAuth";
import { useI18n } from "../lib/i18n";

const executionModes: AiExecutionMode[] = ["free_only", "local_only", "any_configured"];
const knowledgePolicies: AiKnowledgePolicy[] = ["verified_only", "trusted_plus", "all_allowed"];

export function AiConsolePage(): JSX.Element {
  const { t } = useI18n();
  const { user } = useAuth();
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
  const isAdmin = user?.role === "admin";

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
      setStreamingText("");
      return sendAiMessageStream(activeId, draft, selectedCitationIds, contextPolicy, (delta) => setStreamingText((current) => current + delta));
    },
    onSuccess: async () => {
      setDraft("");
      setStreamingText("");
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
                  <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
                    {(session.messages ?? []).map((message) => (
                      <article key={message.id} className={`max-w-[92%] rounded-xl p-3 ${message.role === "user" ? "ml-auto bg-raven-violet/20" : "bg-raven-panelSoft"}`}>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-raven-muted">{message.role === "assistant" ? `${t("AI-generated analysis")} · ${message.provider_id}/${message.model_id}` : t("You")}</p>
                        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                        {message.role === "assistant" && message.citation_validation?.unverified_response_references.length ? <p className="mt-2 text-xs text-amber-300">{t("Unverified citation references")}: {message.citation_validation.unverified_response_references.join(", ")}</p> : null}
                        {message.supplied_citations.length ? <div className="mt-2 border-t border-raven-border pt-2 text-xs text-raven-muted"><span className="font-semibold">{t("Sources used")}: </span>{message.supplied_citations.join(", ")}</div> : null}
                      </article>
                    ))}
                    {streamingText ? <article className="max-w-[92%] rounded-xl bg-raven-panelSoft p-3" aria-live="polite"><p className="mb-1 text-xs font-semibold uppercase tracking-wide text-raven-muted">{t("AI-generated analysis")} · {session.provider_id}/{session.model_id}</p><p className="whitespace-pre-wrap text-sm leading-6">{streamingText}</p></article> : null}
                    {session.status === "running" ? <div className="flex items-center gap-2 text-sm text-raven-muted"><Sparkles size={15} className="animate-pulse" />{t("Generating response")}</div> : null}
                    {session.status === "failed" ? <p role="status" className="text-sm text-amber-300">{t("The provider request failed. Your session is preserved and RavenTech core services remain available.")}</p> : null}
                  </div>
                  <div className="border-t border-raven-border p-4">
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
                    <p className="mt-2 text-xs text-raven-muted">{t("AI-generated analysis is separate from verified RavenTech evidence. Only selected Knowledge excerpts are shared with the selected model.")}</p>
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
            </div>
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
