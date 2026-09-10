import { AlertTriangle, Loader2, RefreshCw, SearchX } from "lucide-react";

import { ApiError } from "../lib/api";
import { useI18n } from "../lib/i18n";

export function LoadingBlock({ label = "Loading" }: { label?: string }): JSX.Element {
  const { t } = useI18n();
  return (
    <div className="flex min-h-40 items-center justify-center rounded-lg border border-raven-border bg-raven-panel/80 text-raven-muted" role="status" aria-live="polite">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
      <span>{t(label)}</span>
    </div>
  );
}

export function ErrorBlock({
  message,
  title = "Unable to load data",
  onRetry,
}: {
  message: string | Error;
  title?: string;
  onRetry?: () => void;
}): JSX.Element {
  const { t } = useI18n();
  const error = normalizeErrorMessage(message);
  return (
    <div
      className="rounded-lg border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100"
      role="alert"
    >
      <div className="flex items-center gap-2 font-medium">
        <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        <span>{t(title)}</span>
      </div>
      <p className="mt-2 break-words text-rose-100/85">{error.summary}</p>
      {error.suggestion ? (
        <p className="mt-2 break-words text-rose-100/70">{error.suggestion}</p>
      ) : null}
      <button
        type="button"
        onClick={onRetry ?? (() => window.location.reload())}
        className="mt-3 inline-flex items-center gap-2 rounded-md border border-rose-300/30 px-3 py-2 text-xs font-medium text-rose-100 hover:bg-rose-500/10"
      >
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
        {t("Retry")}
      </button>
      {error.details.length ? (
        <details className="mt-3 rounded-md border border-rose-300/20 bg-raven-bg/40 p-3">
          <summary className="cursor-pointer text-xs font-medium text-rose-100/80">
            {t("Technical details")}
          </summary>
          <dl className="mt-3 space-y-2 text-xs text-rose-100/70">
            {error.details.map((item) => (
              <div
                key={item.label}
                className="grid gap-1 sm:grid-cols-[120px_minmax(0,1fr)]"
              >
                <dt className="text-rose-100/50">{item.label}</dt>
                <dd className="break-words font-mono">{item.value}</dd>
              </div>
            ))}
          </dl>
        </details>
      ) : null}
    </div>
  );
}

export function EmptyBlock({
  title = "Nothing here yet",
  message,
  nextStep,
  permission,
}: {
  title?: string;
  message: string;
  nextStep?: string;
  permission?: string;
}): JSX.Element {
  const { t } = useI18n();
  return (
    <div className="rounded-lg border border-dashed border-raven-border bg-raven-panel/60 p-8 text-center text-sm text-raven-muted">
      <SearchX className="mx-auto mb-3 h-5 w-5 text-raven-muted" aria-hidden="true" />
      <p className="font-medium text-raven-text">{t(title)}</p>
      <p className="mx-auto mt-2 max-w-2xl leading-6">{t(message)}</p>
      {nextStep ? (
        <p className="mx-auto mt-2 max-w-2xl text-raven-text">{t(nextStep)}</p>
      ) : null}
      {permission ? (
        <p className="mx-auto mt-2 max-w-2xl text-xs">{t(permission)}</p>
      ) : null}
    </div>
  );
}

function normalizeErrorMessage(message: string | Error): {
  summary: string;
  suggestion?: string;
  details: Array<{ label: string; value: string }>;
} {
  if (message instanceof ApiError) {
    return {
      summary: message.message,
      suggestion: message.metadata.suggestion,
      details: [
        message.endpoint ? { label: "Endpoint", value: message.endpoint } : null,
        message.status ? { label: "Status", value: String(message.status) } : null,
        message.metadata.category
          ? { label: "Category", value: message.metadata.category }
          : null,
        message.metadata.detail
          ? { label: "Detail", value: message.metadata.detail }
          : null,
        message.metadata.requestId
          ? { label: "Request ID", value: message.metadata.requestId }
          : null,
      ].filter((item): item is { label: string; value: string } => item !== null),
    };
  }

  const rawMessage = message instanceof Error ? message.message : message;
  const parsed = parseLegacyApiMessage(rawMessage);
  if (parsed) {
    return parsed;
  }
  return {
    summary: rawMessage || "Something went wrong.",
    details: [],
  };
}

function parseLegacyApiMessage(message: string):
  | {
      summary: string;
      suggestion?: string;
      details: Array<{ label: string; value: string }>;
    }
  | null {
  const lines = message.split("\n").map((line) => line.trim()).filter(Boolean);
  const fields = new Map<string, string>();
  for (const line of lines) {
    const separator = line.indexOf(":");
    if (separator > 0) {
      fields.set(line.slice(0, separator), line.slice(separator + 1).trim());
    }
  }
  if (!fields.has("Endpoint") && !fields.has("Status") && !fields.has("Category")) {
    return null;
  }
  const status = fields.get("Status") ?? "";
  const category = fields.get("Category") ?? "";
  const detail = fields.get("Detail");
  const summary =
    status === "401"
      ? "Authentication required. Sign in again."
      : status === "403"
        ? "This action requires additional permissions."
        : status === "404"
          ? "The requested item could not be found."
          : category === "Backend unreachable"
            ? "Backend temporarily unavailable."
            : Number(status) >= 500
              ? "Backend temporarily unavailable."
              : detail || "The request could not be completed.";
  return {
    summary,
    suggestion: fields.get("Suggested action"),
    details: Array.from(fields.entries()).map(([label, value]) => ({
      label,
      value,
    })),
  };
}
