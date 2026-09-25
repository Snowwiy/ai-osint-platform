import { BookOpen, Check, Copy, FolderOpen, RadioTower, RefreshCw, Search, ShieldCheck, Trash2, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import {
  getDetectionKnowledge,
  getFrameworkKnowledge,
  getIocGuidance,
  addObsidianVault,
  uploadKnowledgeDocuments,
  listKnowledgeSources,
  getKnowledgeStats,
  listKnowledgeDocuments,
  getKnowledgeDocument,
  replaceKnowledgeSourceFiles,
  syncKnowledgeSource,
  updateKnowledgeSource,
  removeKnowledgeSource,
  searchKnowledge,
} from "../lib/api";
import type {
  DetectionKnowledgeCard,
  IOCGuidanceCard,
  KnowledgeSearchResponse,
  KnowledgeSearchResult,
  KnowledgeSource,
  KnowledgeDocumentSummary,
} from "../types";
import { useAuth } from "../lib/useAuth";
import { useI18n } from "../lib/i18n";
import { nativeKnowledgePickerAvailable, selectNativeKnowledgeFiles } from "../lib/nativeKnowledgePicker";

const examples = [
  "exposed RDP defensive controls",
  "SPF and DMARC mitigation",
  "NIST incident response containment",
  "OWASP access control guidance",
];
const knowledgeCategories = [
  "Cybersecurity", "OSINT", "DFIR", "Threat Intelligence", "Networking",
  "Cloud", "Windows", "Linux", "MITRE ATT&CK", "NIST", "CIS", "OWASP",
  "ISO", "Sigma", "YARA", "Forensics", "Incident Response",
  "Internal Procedures", "Scripts & Automation", "Development", "Other",
];

export function KnowledgeSearchPage(): JSX.Element {
  const { user } = useAuth();
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [filterSource, setFilterSource] = useState("");
  const [filterTrust, setFilterTrust] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [filterLanguage, setFilterLanguage] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterTags, setFilterTags] = useState("");
  const sourceOptions = useQuery({ queryKey: ["knowledge-sources"], queryFn: listKnowledgeSources });
  const search = useMutation<KnowledgeSearchResponse, Error, string>({
    mutationFn: (value) => searchKnowledge(value, {
      source_id: filterSource || undefined,
      trust_level: filterTrust || undefined,
      verified_only: verifiedOnly,
      language: filterLanguage || undefined,
      category: filterCategory || undefined,
      tags: filterTags.split(",").map((tag) => tag.trim()).filter(Boolean),
    }),
  });
  const detections = useQuery({
    queryKey: ["knowledge-detections"],
    queryFn: () => getDetectionKnowledge(),
  });
  const frameworks = useQuery({
    queryKey: ["knowledge-frameworks"],
    queryFn: getFrameworkKnowledge,
  });
  const iocGuidance = useQuery({
    queryKey: ["knowledge-ioc-guidance"],
    queryFn: () => getIocGuidance(),
  });

  function submitQuery(value: string): void {
    const clean = value.trim();
    if (clean.length < 2) {
      setValidationError("Enter at least two characters to search.");
      return;
    }
    setValidationError(null);
    search.reset();
    search.mutate(clean);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    submitQuery(query);
  }

  const searchItems = search.data?.items ?? [];
  const detectionItems = detections.data?.items ?? [];
  const iocGuidanceItems = iocGuidance.data?.items ?? [];

  return (
    <>
      <PageHeader title={t("Knowledge Search")} eyebrow={t("Local defensive knowledge")} />
      <KnowledgeSourceCenter isAdmin={user?.role === "admin"} />
      <section className="mb-6 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <div className="flex items-start gap-3">
          <ShieldCheck
            className="mt-0.5 h-5 w-5 flex-none text-cyan-300"
            aria-hidden="true"
          />
          <div>
            <h2 className="font-semibold">{t("Search curated defensive guidance")}</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-raven-muted">
              {t("Searches RavenTech's indexed local knowledge. This search does not browse the internet or execute security actions.")}
            </p>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="mt-5 flex flex-col gap-3 md:flex-row"
        >
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setValidationError(null);
            }}
            placeholder={t("Search a control, mitigation, framework, or defensive topic")}
            aria-label={t("Knowledge search query")}
            className="min-w-0 flex-1 rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
          />
          <button
            type="submit"
            disabled={search.isPending || query.trim().length < 2}
            className="inline-flex items-center justify-center gap-2 rounded-md bg-raven-violet px-4 py-2 font-medium text-white hover:bg-violet-500 disabled:opacity-50"
          >
            <Search className="h-4 w-4" aria-hidden="true" />
            {search.isPending ? t("Searching") : t("Search knowledge")}
          </button>
        </form>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <label className="text-xs text-raven-muted">{t("Source")}<select value={filterSource} onChange={(event) => setFilterSource(event.target.value)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"><option value="">{t("All local sources")}</option>{(sourceOptions.data?.items ?? []).map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}</select></label>
          <label className="text-xs text-raven-muted">{t("Trust level")}<select value={filterTrust} onChange={(event) => setFilterTrust(event.target.value)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"><option value="">{t("Any trust level")}</option><option value="authoritative">{t("Authoritative")}</option><option value="trusted">{t("Trusted")}</option><option value="internal">{t("Internal")}</option><option value="community">{t("Community")}</option><option value="unknown">{t("Unknown")}</option></select></label>
          <label className="text-xs text-raven-muted">{t("Language")}<input value={filterLanguage} onChange={(event) => setFilterLanguage(event.target.value)} maxLength={16} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text" placeholder="en" /></label>
          <label className="text-xs text-raven-muted">{t("Category")}<select value={filterCategory} onChange={(event) => setFilterCategory(event.target.value)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"><option value="">{t("All categories")}</option>{knowledgeCategories.map(category => <option key={category} value={category}>{t(category)}</option>)}</select></label>
          <label className="text-xs text-raven-muted">{t("Tags")}<input value={filterTags} onChange={(event) => setFilterTags(event.target.value)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text" placeholder="windows, hardening" /></label>
          <label className="flex items-center gap-2 self-end pb-2 text-sm text-raven-muted"><input type="checkbox" checked={verifiedOnly} onChange={(event) => setVerifiedOnly(event.target.checked)} />{t("Verified sources only")}</label>
        </div>

        {validationError ? (
          <p className="mt-2 text-sm text-rose-200">{validationError}</p>
        ) : null}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase text-raven-muted">Examples</span>
          {examples.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => {
                setQuery(example);
                submitQuery(example);
              }}
              disabled={search.isPending}
              className="rounded border border-raven-border px-2.5 py-1 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text disabled:opacity-50"
            >
              {example}
            </button>
          ))}
        </div>
      </section>

      {search.isPending ? <LoadingBlock label="Searching local knowledge" /> : null}
      {search.isError ? <ErrorBlock message={search.error} /> : null}
      {search.data ? (
        searchItems.length ? (
          <section className="space-y-4">
            <p className="text-sm text-raven-muted">
              {search.data.total} result{search.data.total === 1 ? "" : "s"} for
              {" "}
              <span className="text-raven-text">{search.data.query}</span>
            </p>
            {searchItems.map((item) => (
              <KnowledgeResultCard
                key={`${item.document_id}-${(item.chunk ?? "").slice(0, 20)}`}
                item={item}
              />
            ))}
          </section>
        ) : (
          <EmptyBlock
            title="No local guidance matched"
            message="The curated local library did not contain a matching defensive reference."
            nextStep="Try a control family, mitigation, framework, or technology name."
          />
        )
      ) : search.isIdle ? (
        <EmptyBlock
          title="Search local defensive knowledge"
          message="This library provides framework guidance, mitigations, and citation-ready references without browsing the internet."
          nextStep="Choose an example above or enter a defensive control, technology, or mitigation."
        />
      ) : null}

      <section className="mt-8">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-raven-cyan">
              Detection engineering library
            </p>
            <h2 className="mt-1 text-lg font-semibold">
              Sigma and YARA defensive references
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-raven-muted">
              Analyst reference material only. Nothing is executed, deployed, or
              evaluated against live systems.
            </p>
          </div>
          <span className="text-xs text-raven-muted">
            {frameworks.data?.total ?? 0} supported knowledge frameworks
          </span>
        </div>
        {detections.isLoading ? (
          <LoadingBlock label="Loading defensive detection references" />
        ) : detections.isError ? (
          <ErrorBlock message={detections.error} />
        ) : detectionItems.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {detectionItems.map((item) => (
              <DetectionReferenceCard key={item.id} item={item} />
            ))}
          </div>
        ) : (
          <EmptyBlock
            title="No detection references available"
            message="The local defensive library does not currently contain Sigma or YARA references."
            nextStep="An administrator can index approved local knowledge sources."
          />
        )}
      </section>

      <section className="mt-8">
        <div className="mb-3">
          <p className="text-xs uppercase tracking-wide text-raven-cyan">
            Threat intelligence knowledge
          </p>
          <h2 className="mt-1 text-lg font-semibold">
            IOC guidance and defensive investigation context
          </h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-raven-muted">
            Local analyst guidance for recurring infrastructure, exposed services,
            DNS posture, authentication telemetry, and remediation. No external
            enrichment is performed.
          </p>
        </div>
        {iocGuidance.isLoading ? (
          <LoadingBlock label="Loading IOC guidance" />
        ) : iocGuidance.isError ? (
          <ErrorBlock message={iocGuidance.error} />
        ) : iocGuidanceItems.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {iocGuidanceItems.map((item) => (
              <IOCGuidanceCardView key={item.id} item={item} />
            ))}
          </div>
        ) : (
          <EmptyBlock
            title="No IOC guidance available"
            message="The local defensive library does not currently contain IOC guidance."
            nextStep="Continue using approved framework and detection references."
          />
        )}
      </section>
    </>
  );
}

function KnowledgeSourceCenter({ isAdmin }: { isAdmin: boolean }): JSX.Element {
  const { t } = useI18n();
  const [sourceName, setSourceName] = useState("");
  const [trustLevel, setTrustLevel] = useState("unknown");
  const [verification, setVerification] = useState("unverified");
  const [category, setCategory] = useState("Other");
  const [publisher, setPublisher] = useState("");
  const [canonicalUrl, setCanonicalUrl] = useState("");
  const [publicationDate, setPublicationDate] = useState("");
  const [sourceVersion, setSourceVersion] = useState("");
  const [sourceNotes, setSourceNotes] = useState("");
  const [selection, setSelection] = useState<File[]>([]);
  const [selectionRootPath, setSelectionRootPath] = useState<string | undefined>();
  const [selectionSkipped, setSelectionSkipped] = useState({ unsupported: 0, oversized: 0 });
  const [pickerError, setPickerError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [sourceMode, setSourceMode] = useState<"vault" | "documents">("vault");
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const sources = useQuery({ queryKey: ["knowledge-sources"], queryFn: listKnowledgeSources });
  const stats = useQuery({ queryKey: ["knowledge-stats"], queryFn: getKnowledgeStats });
  const documents = useQuery({
    queryKey: ["knowledge-source-documents", selectedSourceId],
    queryFn: () => listKnowledgeDocuments(selectedSourceId!),
    enabled: Boolean(selectedSourceId),
  });
  const refreshQueries = async (): Promise<void> => {
    await Promise.all([sources.refetch(), stats.refetch(), documents.refetch()]);
  };
  const upload = useMutation({
    mutationFn: async (): Promise<KnowledgeSource> => {
      if (!selection.length) throw new Error("Select at least one supported file.");
      const firstFile = selection[0] as (File & { webkitRelativePath?: string }) | undefined;
      const name = sourceName.trim() || firstFile?.webkitRelativePath?.split("/")[0] || firstFile?.name || "Local documents";
      return sourceMode === "vault"
        ? addObsidianVault(name, selection, trustLevel, verification, category, {
          publisher, canonicalUrl, publicationDate, version: sourceVersion, notes: sourceNotes,
          }, selectionRootPath)
        : uploadKnowledgeDocuments(name, selection, trustLevel, verification, {
            publisher, canonicalUrl, publicationDate, version: sourceVersion, category, notes: sourceNotes,
          });
    },
    onSuccess: async (source) => {
      setSelection([]);
      setSelectionRootPath(undefined);
      setSelectionSkipped({ unsupported: 0, oversized: 0 });
      setSourceName("");
      setPublisher("");
      setCanonicalUrl("");
      setPublicationDate("");
      setSourceVersion("");
      setSourceNotes("");
      setSelectedSourceId(source.id);
      await refreshQueries();
    },
  });
  const sync = useMutation({ mutationFn: syncKnowledgeSource, onSuccess: refreshQueries });
  const relink = useMutation({ mutationFn: ({ id, files, rootPath }: { id: string; files: File[]; rootPath?: string }) => replaceKnowledgeSourceFiles(id, files, rootPath), onSuccess: refreshQueries });
  const patch = useMutation({ mutationFn: ({ id, values }: { id: string; values: Partial<KnowledgeSource> }) => updateKnowledgeSource(id, values), onSuccess: refreshQueries });
  const remove = useMutation({ mutationFn: removeKnowledgeSource, onSuccess: refreshQueries });
  const sourceItems = sources.data?.items ?? [];
  const selectedSource = useMemo(
    () => sourceItems.find((source) => source.id === selectedSourceId) ?? null,
    [sourceItems, selectedSourceId],
  );

  function readSelection(input: HTMLInputElement): void {
    setSelection(Array.from(input.files ?? []));
    setSelectionRootPath(undefined);
    setSelectionSkipped({ unsupported: 0, oversized: 0 });
    setPickerError(null);
    upload.reset();
  }

  async function chooseSelection(): Promise<void> {
    setPickerError(null);
    if (!nativeKnowledgePickerAvailable()) {
      fileInput.current?.click();
      return;
    }
    try {
      const picked = await selectNativeKnowledgeFiles(sourceMode);
      if (!picked) return;
      setSelection(picked.files);
      setSelectionRootPath(picked.rootPath);
      setSelectionSkipped({ unsupported: picked.unsupportedCount, oversized: picked.oversizedCount });
      upload.reset();
    } catch (error) {
      setPickerError(error instanceof Error ? error.message : t("Native file selection failed"));
    }
  }

  async function chooseRelink(source: KnowledgeSource): Promise<void> {
    setPickerError(null);
    try {
      if (nativeKnowledgePickerAvailable()) {
        const picked = await selectNativeKnowledgeFiles(source.source_type === "obsidian_vault" ? "vault" : "documents");
        if (!picked) return;
        if (!picked.files.length) throw new Error("No supported documents were selected.");
        await relink.mutateAsync({ id: source.id, files: picked.files, rootPath: picked.rootPath });
        return;
      }
      throw new Error("Select local Knowledge sources from the RavenTech desktop application.");
    } catch (error) {
      setPickerError(error instanceof Error ? error.message : t("Native file selection failed"));
    }
  }

  return (
      <section className="mb-6 rounded-lg border border-raven-border bg-raven-panel/85 p-5" aria-label={t("Knowledge Source Center")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <BookOpen className="mt-0.5 h-5 w-5 text-cyan-300" aria-hidden="true" />
          <div>
            <h2 className="font-semibold">{t("Knowledge Source Center")}</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-raven-muted">{t("Build a local library from selected Obsidian notes and reference documents. Imported material stays on this RavenTech installation; it is not uploaded to an external provider.")}</p>
            <p className="mt-2 max-w-3xl text-xs text-raven-muted">{t("Knowledge snapshot notice")}</p>
          </div>
        </div>
        <button type="button" onClick={() => void refreshQueries()} className="rounded border border-raven-border p-2 text-raven-muted hover:text-raven-text" aria-label="Refresh Knowledge sources"><RefreshCw className="h-4 w-4" /></button>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-sm md:grid-cols-4 xl:grid-cols-8">
        {[
          ["Sources", stats.data?.sources], ["Documents", stats.data?.documents], ["Indexed chunks", stats.data?.chunks], ["Verified sources", stats.data?.verified_sources], ["Last sync", stats.data?.last_sync_at ? new Date(stats.data.last_sync_at).toLocaleString() : "—"],
          ["Unverified sources", stats.data?.unverified_sources], ["Failed documents", stats.data?.failed_documents], ["Offline sources", stats.data?.offline_sources], ["Active indexing jobs", stats.data?.active_jobs],
        ].map(([label, value]) => <div key={String(label)} className="rounded border border-raven-border bg-raven-panelSoft p-3"><p className="text-xs text-raven-muted">{t(String(label))}</p><p className="mt-1 font-semibold">{value ?? "—"}</p></div>)}
      </div>

      {isAdmin ? (
        <div className="mt-4 rounded-md border border-raven-border bg-raven-panelSoft p-4">
          <h3 className="font-medium">{t("Add a local source")}</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <label className="text-xs text-raven-muted">{t("Source name")}<input value={sourceName} onChange={(event) => setSourceName(event.target.value)} maxLength={200} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text" placeholder={t("My security vault")} /></label>
            <label className="text-xs text-raven-muted">{t("Category")}<select value={category} onChange={(event) => setCategory(event.target.value)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text">{knowledgeCategories.map(value => <option key={value} value={value}>{t(value)}</option>)}</select></label>
            <label className="text-xs text-raven-muted">{t("Trust")}<select value={trustLevel} onChange={(event) => setTrustLevel(event.target.value)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"><option value="unknown">{t("Unknown")}</option><option value="internal">{t("Internal")}</option><option value="community">{t("Community")}</option><option value="trusted">{t("Trusted")}</option><option value="authoritative">{t("Authoritative")}</option></select></label>
            <label className="text-xs text-raven-muted">{t("Verification")}<select value={verification} onChange={(event) => setVerification(event.target.value)} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"><option value="unverified">{t("Unverified")}</option><option value="reviewed">{t("Reviewed")}</option><option value="verified">{t("Verified")}</option></select></label>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="text-xs text-raven-muted">Organization / publisher<input value={publisher} onChange={(event) => setPublisher(event.target.value)} maxLength={200} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text" /></label>
            <label className="text-xs text-raven-muted">Canonical reference URL<input value={canonicalUrl} onChange={(event) => setCanonicalUrl(event.target.value)} maxLength={1000} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text" placeholder="https://…" /></label>
            <label className="text-xs text-raven-muted">Publication date<input value={publicationDate} onChange={(event) => setPublicationDate(event.target.value)} maxLength={40} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text" placeholder="YYYY-MM-DD" /></label>
            <label className="text-xs text-raven-muted">Document version<input value={sourceVersion} onChange={(event) => setSourceVersion(event.target.value)} maxLength={120} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text" /></label>
            <label className="text-xs text-raven-muted">Source notes<input value={sourceNotes} onChange={(event) => setSourceNotes(event.target.value)} maxLength={2000} className="mt-1 w-full rounded border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text" /></label>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => setSourceMode("vault")} className={`rounded border px-3 py-2 text-sm ${sourceMode === "vault" ? "border-raven-violet text-raven-text" : "border-raven-border text-raven-muted"}`}><FolderOpen className="mr-2 inline h-4 w-4" />{t("Obsidian vault")}</button>
            <button type="button" onClick={() => setSourceMode("documents")} className={`rounded border px-3 py-2 text-sm ${sourceMode === "documents" ? "border-raven-violet text-raven-text" : "border-raven-border text-raven-muted"}`}><Upload className="mr-2 inline h-4 w-4" />{t("Upload documents")}</button>
            <button type="button" onClick={() => void chooseSelection()} className="cursor-pointer rounded bg-raven-violet px-3 py-2 text-sm font-medium text-white hover:bg-violet-500">{sourceMode === "vault" ? t("Choose vault folder") : t("Choose documents")}</button>
            <input ref={fileInput} type="file" multiple onChange={(event) => readSelection(event.currentTarget)} {...(sourceMode === "vault" ? { webkitdirectory: "", directory: "" } as Record<string, string> : {})} className="sr-only" aria-label={t("Choose documents")} />
            <span className="text-xs text-raven-muted">{selection.length} {t("selected")}</span>
            {selection.length ? <span className="text-xs text-raven-muted">{selection.filter(isSupportedKnowledgeFile).length} {t("supported")} · {selectionSkipped.unsupported + selection.filter((file) => !isSupportedKnowledgeFile(file)).length} {t("unsupported")} · {selectionSkipped.oversized} {t("too large")} · {formatBytes(selection.reduce((total, file) => total + file.size, 0))} {t("selected")}</span> : null}
            <button type="button" disabled={!selection.length || upload.isPending} onClick={() => upload.mutate()} className="rounded border border-raven-border px-3 py-2 text-sm disabled:opacity-50">{upload.isPending ? t("Queueing index") : t("Add and index")}</button>
          </div>
          {pickerError ? <p role="alert" className="mt-2 text-sm text-rose-200">{pickerError}</p> : null}
          {upload.isError ? <p role="alert" className="mt-2 text-sm text-rose-200">{upload.error.message}</p> : null}
        </div>
      ) : null}

      {sources.isLoading ? <p className="mt-4 text-sm text-raven-muted">Loading local sources…</p> : null}
      {sourceItems.length ? <div className="mt-4 space-y-3">{sourceItems.map((source) => (
        <article key={source.id} className="rounded-md border border-raven-border p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <button type="button" onClick={() => setSelectedSourceId(selectedSourceId === source.id ? null : source.id)} className="min-w-0 text-left">
              <span className="font-medium">{source.name}</span><span className="ml-2 rounded border border-raven-border px-2 py-0.5 text-xs text-raven-muted">{t(source.status)}</span>
              <span className="mt-1 block text-xs text-raven-muted">{source.display_location} · {t(source.category)} · {source.document_count} {t("Documents")} · {source.chunk_count} {t("Indexed chunks")} · {t(source.trust_level)} / {t(source.verification_status)}</span>
              {Object.keys(source.scan_counts).length ? <span className="mt-1 block text-xs text-raven-muted">{t("Indexed")}: {source.scan_counts.indexed ?? 0} · {t("Unsupported")}: {source.scan_counts.unsupported ?? 0} · {t("Failed documents")}: {source.scan_counts.failed ?? 0} · {t("Too large")}: {source.scan_counts.oversized ?? 0}</span> : null}
              {source.error_summary ? <span className="mt-1 block text-xs text-amber-200">{source.error_summary}</span> : null}
            </button>
            {isAdmin ? <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => sync.mutate(source.id)} disabled={sync.isPending} className="rounded border border-raven-border px-2 py-1 text-xs">{t(source.source_type === "obsidian_vault" ? "Sync selected vault" : "Sync imported snapshot")}</button>
              <button type="button" onClick={() => void chooseRelink(source)} disabled={relink.isPending} className="rounded border border-raven-border px-2 py-1 text-xs">{t(source.availability === "offline" ? "Relink selected source" : "Refresh selected source")}</button>
              <select aria-label={`${t("Trust")} ${source.name}`} value={source.trust_level} onChange={(event) => patch.mutate({ id: source.id, values: { trust_level: event.target.value } })} className="rounded border border-raven-border bg-raven-bg px-2 py-1 text-xs"><option value="unknown">{t("Unknown")}</option><option value="internal">{t("Internal")}</option><option value="community">{t("Community")}</option><option value="trusted">{t("Trusted")}</option><option value="authoritative">{t("Authoritative")}</option></select>
              <select aria-label={`${t("Category")} ${source.name}`} value={source.category} onChange={(event) => patch.mutate({ id: source.id, values: { category: event.target.value } })} className="rounded border border-raven-border bg-raven-bg px-2 py-1 text-xs">{knowledgeCategories.map(value => <option key={value} value={value}>{t(value)}</option>)}</select>
              <select aria-label={`${t("Verification")} ${source.name}`} value={source.verification_status} onChange={(event) => patch.mutate({ id: source.id, values: { verification_status: event.target.value } })} className="rounded border border-raven-border bg-raven-bg px-2 py-1 text-xs"><option value="unverified">{t("Unverified")}</option><option value="reviewed">{t("Reviewed")}</option><option value="verified">{t("Verified")}</option><option value="stale">{t("Stale")}</option><option value="rejected">{t("Rejected")}</option></select>
              <KnowledgeSourceMetadataEditor source={source} onSave={(values) => patch.mutate({ id: source.id, values })} saving={patch.isPending} />
              <button type="button" onClick={() => patch.mutate({ id: source.id, values: { status: source.status === "disabled" ? "enabled" : "disabled" } })} className="rounded border border-raven-border px-2 py-1 text-xs">{source.status === "disabled" ? t("Enable") : t("Disable")}</button>
              <button type="button" onClick={() => { if (window.confirm(t("Remove this source from the RavenTech index? Original selected files are not deleted."))) remove.mutate(source.id); }} aria-label={`${t("Remove")} ${source.name}`} className="rounded border border-raven-border p-1 text-rose-200"><Trash2 className="h-4 w-4" /></button>
            </div> : null}
          </div>
          {selectedSourceId === source.id ? <div className="mt-3 border-t border-raven-border pt-3">
            <p className="text-xs uppercase text-raven-muted">Indexed documents</p>
            {documents.isLoading ? <p className="mt-2 text-sm text-raven-muted">{t("Loading documents")}</p> : <ul className="mt-2 space-y-2">{(documents.data?.items ?? []).map((document) => <KnowledgeDocumentRow key={document.id} document={document} />)}</ul>}
          </div> : null}
        </article>
      ))}</div> : !sources.isLoading ? <p className="mt-4 rounded border border-dashed border-raven-border p-4 text-sm text-raven-muted">{t("No custom knowledge sources yet. Add an Obsidian vault or select trusted reference documents to build the local knowledge base. Built-in framework references remain available.")}</p> : null}
      {selectedSource ? <span className="sr-only">Selected source {selectedSource.name}</span> : null}
    </section>
  );
}

function KnowledgeDocumentRow({ document }: { document: KnowledgeDocumentSummary }): JSX.Element {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const detail = useQuery({
    queryKey: ["knowledge-document-detail", document.id],
    queryFn: () => getKnowledgeDocument(document.id),
    enabled: open,
  });
  return <li className="rounded bg-raven-panelSoft p-2 text-sm">
    <button type="button" aria-expanded={open} onClick={() => setOpen(value => !value)} className="w-full text-left">
      <span className="font-medium">{document.title}</span>
      <span className="ml-2 text-xs text-raven-muted">{document.relative_name} · {document.content_type} · {t(document.category)} · {t(document.trust_level)}/{t(document.verification_status)}</span>
    </button>
    {document.document_status === "sensitive_content_warning" ? <p className="mt-1 text-xs text-amber-200">{t("Sensitive content warning. Review before sharing or adding this reference to an external report.")}</p> : null}
      <div className="mt-1 flex flex-wrap gap-1">{document.tags.map(tag => <span key={tag} className="rounded border border-raven-border px-1.5 py-0.5 text-xs text-raven-muted">{tag}</span>)}</div>
    {open ? detail.isLoading ? <p className="mt-2 text-xs text-raven-muted">{t("Loading document preview")}</p> : detail.isError ? <p role="alert" className="mt-2 text-xs text-rose-200">{t("Document preview unavailable")}</p> : detail.data ? <div className="mt-3 space-y-2 border-t border-raven-border pt-3">
      <dl className="grid gap-2 text-xs sm:grid-cols-2">
        <div><dt className="text-raven-muted">{t("Source")}</dt><dd>{detail.data.source_name ?? "—"}</dd></div>
        <div><dt className="text-raven-muted">{t("Language")}</dt><dd>{detail.data.language ?? t("Unknown")}</dd></div>
        <div><dt className="text-raven-muted">{t("Modified")}</dt><dd>{detail.data.modified_at ? new Date(detail.data.modified_at).toLocaleString() : "—"}</dd></div>
        <div><dt className="text-raven-muted">{t("Indexed")}</dt><dd>{detail.data.indexed_at ? new Date(detail.data.indexed_at).toLocaleString() : "—"}</dd></div>
        <div className="sm:col-span-2"><dt className="text-raven-muted">SHA-256</dt><dd className="break-all">{detail.data.hash}</dd></div>
      </dl>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded border border-raven-border p-3 text-xs leading-5">{detail.data.content}</pre>
      {detail.data.references.length ? <div><h4 className="text-xs font-medium">{t("Related notes")}</h4><ul className="mt-1 space-y-1">{detail.data.references.map((link, index) => <li key={`${link.target}-${index}`} className="text-xs text-raven-muted">{link.kind}: {link.alias ?? link.target} · {link.resolved ? t("Resolved") : t("Unresolved")}</li>)}</ul></div> : null}
    </div> : null : null}
  </li>;
}

function KnowledgeSourceMetadataEditor({
  source,
  onSave,
  saving,
}: {
  source: KnowledgeSource;
  onSave: (values: Partial<KnowledgeSource>) => void;
  saving: boolean;
}): JSX.Element {
  const { t } = useI18n();
  const [publisher, setPublisher] = useState(source.publisher ?? "");
  const [canonicalUrl, setCanonicalUrl] = useState(source.canonical_url ?? "");
  const [publicationDate, setPublicationDate] = useState(source.publication_date ?? "");
  const [version, setVersion] = useState(source.version_label ?? "");
  const [notes, setNotes] = useState(source.notes ?? "");
  useEffect(() => {
    setPublisher(source.publisher ?? "");
    setCanonicalUrl(source.canonical_url ?? "");
    setPublicationDate(source.publication_date ?? "");
    setVersion(source.version_label ?? "");
    setNotes(source.notes ?? "");
  }, [source.id, source.publisher, source.canonical_url, source.publication_date, source.version_label, source.notes]);
  return (
    <details className="rounded border border-raven-border px-2 py-1 text-xs">
      <summary className="cursor-pointer">{t("Review source metadata")}</summary>
      <div className="mt-2 grid min-w-64 gap-2">
        <input aria-label={t("Publisher")} value={publisher} onChange={(event) => setPublisher(event.target.value)} maxLength={200} placeholder={t("Publisher")} className="rounded border border-raven-border bg-raven-bg px-2 py-1 text-raven-text" />
        <input aria-label={t("Canonical reference URL")} value={canonicalUrl} onChange={(event) => setCanonicalUrl(event.target.value)} maxLength={1000} placeholder={t("Canonical reference URL")} className="rounded border border-raven-border bg-raven-bg px-2 py-1 text-raven-text" />
        <input aria-label={t("Publication date")} value={publicationDate} onChange={(event) => setPublicationDate(event.target.value)} maxLength={40} placeholder={t("Publication date")} className="rounded border border-raven-border bg-raven-bg px-2 py-1 text-raven-text" />
        <input aria-label={t("Document version")} value={version} onChange={(event) => setVersion(event.target.value)} maxLength={120} placeholder={t("Document version")} className="rounded border border-raven-border bg-raven-bg px-2 py-1 text-raven-text" />
        <textarea aria-label={t("Source notes")} value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={2000} placeholder={t("Source notes")} className="rounded border border-raven-border bg-raven-bg px-2 py-1 text-raven-text" />
        <button type="button" disabled={saving} onClick={() => onSave({ publisher, canonical_url: canonicalUrl, publication_date: publicationDate, version_label: version, notes })} className="rounded border border-raven-border px-2 py-1 disabled:opacity-50">{t("Save source metadata")}</button>
      </div>
    </details>
  );
}

const SUPPORTED_KNOWLEDGE_EXTENSIONS = new Set(["md", "txt", "pdf", "docx", "html", "htm", "json", "csv"]);

function isSupportedKnowledgeFile(file: File): boolean {
  const extension = file.name.toLowerCase().split(".").pop() ?? "";
  return SUPPORTED_KNOWLEDGE_EXTENSIONS.has(extension);
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function KnowledgeResultCard({
  item,
}: {
  item: KnowledgeSearchResult;
}): JSX.Element {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const reference = `${item.source_name ?? item.source_type} | ${item.relative_name ?? item.file_path}${item.section ? ` | ${item.section}` : ""}${item.page_number ? ` | ${t("Page")} ${item.page_number}` : ""} | ${item.citation_id ?? item.document_id}`;
  const remediationGuidance = safeStringArray(item.remediation_guidance);
  const tags = safeStringArray(item.tags);
  const score =
    typeof item.score === "number" && Number.isFinite(item.score)
      ? item.score
      : 0;

  async function copyReference(): Promise<void> {
    try {
      await window.navigator.clipboard.writeText(reference);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  }

  return (
    <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="break-words font-semibold">{item.title}</h2>
          <p className="mt-1 text-xs text-raven-muted">
            {item.source_name ?? item.framework ?? item.source_type} | {item.category} | {t("Trust")}: {t(item.trust_level ?? "unknown")} / {t(item.verification_status ?? "unverified")}{item.section ? ` | ${item.section}` : ""}{item.page_number ? ` | ${t("Page")} ${item.page_number}` : ""} | {t("Relevance")}{" "}
            {score.toFixed(2)}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void copyReference()}
          className="inline-flex flex-none items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {copied ? t("Copied") : t("Copy citation")}
        </button>
      </div>

      <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-raven-muted">
        {item.chunk ?? "No excerpt is available for this reference."}
      </p>
      {item.duplicate_of_document_id ? <p className="mt-2 text-xs text-raven-muted">{t("Exact content duplicate")}: {item.duplicate_of_document_id}</p> : null}
      {item.sensitive_content_warning ? <p className="mt-3 rounded border border-amber-400/40 bg-amber-500/10 p-2 text-xs text-amber-100">{t("Sensitive content warning. Review before sharing or adding this reference to an external report.")}</p> : null}

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <KnowledgeContext
          title="Why this matters"
          text={item.why_this_matters}
        />
        <KnowledgeContext
          title="Defensive explanation"
          text={item.defensive_explanation}
        />
        {item.mitre_relevance ? (
          <KnowledgeContext title="MITRE relevance" text={item.mitre_relevance} />
        ) : null}
        {item.sigma_relevance ? (
          <KnowledgeContext title="Sigma relevance" text={item.sigma_relevance} />
        ) : null}
      </div>

      {remediationGuidance.length ? (
        <div className="mt-4">
          <p className="text-xs uppercase text-raven-muted">
            Remediation guidance
          </p>
          <ul className="mt-2 space-y-1 text-sm text-raven-muted">
            {remediationGuidance.map((guidance) => (
              <li key={guidance} className="break-words">
                {guidance}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <dl className="mt-4 grid min-w-0 gap-3 text-xs sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="uppercase text-raven-muted">{t("Document reference")}</dt>
          <dd className="mt-1 break-all text-raven-text" title={item.file_path}>
            {item.file_path}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="uppercase text-raven-muted">{t("Citation")}</dt>
          <dd className="mt-1 break-all text-raven-text">{item.citation_id ?? item.document_id}</dd>
        </div>
      </dl>

      {tags.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {tags.map((tag) => (
            <span
              key={tag}
              className="rounded border border-raven-border px-2 py-0.5 text-xs text-raven-muted"
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function KnowledgeContext({
  title,
  text,
}: {
  title: string;
  text: string;
}): JSX.Element {
  return (
    <div className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs uppercase text-raven-muted">{title}</p>
      <p className="mt-2 break-words text-sm leading-6 text-raven-text">{text}</p>
    </div>
  );
}

function DetectionReferenceCard({
  item,
}: {
  item: DetectionKnowledgeCard;
}): JSX.Element {
  const [copied, setCopied] = useState(false);
  const references = safeStringArray(item.references);
  async function copyReference(): Promise<void> {
    try {
      await window.navigator.clipboard.writeText(
        `${item.id} | ${item.title} | ${references.join(", ")}`,
      );
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  }
  return (
    <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs uppercase tracking-wide text-raven-cyan">
            <RadioTower className="h-4 w-4" aria-hidden="true" />
            {item.framework} | {item.category}
          </p>
          <h3 className="mt-2 break-words font-semibold">{item.title}</h3>
        </div>
        <button
          type="button"
          onClick={() => void copyReference()}
          className="inline-flex flex-none items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {copied ? "Copied" : "Copy reference"}
        </button>
      </div>
      <p className="mt-3 text-sm leading-6 text-raven-muted">
        {item.description}
      </p>
      {item.log_source ? (
        <p className="mt-3 text-sm text-raven-text">
          <span className="text-raven-muted">Log source:</span> {item.log_source}
        </p>
      ) : null}
      <div className="mt-3 rounded-md border border-raven-border bg-raven-panelSoft p-3">
        <p className="text-xs uppercase text-raven-muted">Detection idea</p>
        <p className="mt-2 text-sm leading-6">{item.detection_idea}</p>
      </div>
      <p className="mt-3 text-sm leading-6 text-raven-muted">
        <span className="font-medium text-raven-text">Why this matters:</span>{" "}
        {item.why_this_matters}
      </p>
    </article>
  );
}

function IOCGuidanceCardView({
  item,
}: {
  item: IOCGuidanceCard;
}): JSX.Element {
  const appliesTo = safeStringArray(item.applies_to);
  return (
    <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <p className="text-xs uppercase tracking-wide text-raven-cyan">
        IOC defensive guidance
      </p>
      <h3 className="mt-2 break-words font-semibold">{item.title}</h3>
      <p className="mt-3 text-sm leading-6 text-raven-muted">
        <span className="font-medium text-raven-text">Why this matters:</span>{" "}
        {item.why_this_matters}
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <GuidanceList title="Monitoring" items={item.monitoring_guidance} />
        <GuidanceList title="Logging" items={item.logging_recommendations} />
        <GuidanceList title="MITRE relevance" items={item.mitre_relevance} />
        <GuidanceList title="Sigma references" items={item.sigma_references} />
      </div>
      <div className="mt-3">
        <GuidanceList title="Remediation" items={item.remediation_guidance} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {appliesTo.map((value) => (
          <span
            key={value}
            className="rounded border border-raven-border px-2 py-1 text-xs text-raven-muted"
          >
            {value}
          </span>
        ))}
      </div>
    </article>
  );
}

function GuidanceList({
  title,
  items,
}: {
  title: string;
  items: string[];
}): JSX.Element {
  const safeItems = safeStringArray(items);
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs uppercase text-raven-muted">{title}</p>
      {safeItems.length ? (
        <ul className="mt-2 space-y-1 text-sm leading-6">
          {safeItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-raven-muted">
          No forced mapping is applied.
        </p>
      )}
    </div>
  );
}

function safeStringArray(value: string[] | null | undefined): string[] {
  return Array.isArray(value) ? value : [];
}
