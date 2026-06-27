import { AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";
import { isRouteErrorResponse, useRouteError } from "react-router-dom";

export function RouteErrorFallback(): JSX.Element {
  const error = useRouteError();
  const detail = routeErrorDetail(error);
  return (
    <main className="flex min-h-screen items-center justify-center bg-raven-bg px-4 py-10 text-raven-text">
      <section className="w-full max-w-2xl rounded-lg border border-rose-400/30 bg-raven-panel/95 p-6 shadow-glow">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-rose-500/15 p-2 text-rose-100">
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-raven-cyan">
              Page failed to load
            </p>
            <h1 className="mt-1 text-2xl font-semibold">
              This workspace view could not be rendered.
            </h1>
            <p className="mt-3 text-sm leading-6 text-raven-muted">
              Refresh the page or go back to a previous workspace view. If this
              keeps happening, expand the technical details and share them with
              the project maintainer.
            </p>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm font-medium text-white hover:bg-violet-500"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Retry page
          </button>
          <button
            type="button"
            onClick={() => window.history.back()}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:border-raven-violet hover:text-raven-text"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Go back
          </button>
        </div>

        <details className="mt-5 rounded-md border border-raven-border bg-raven-bg/50 p-3">
          <summary className="cursor-pointer text-sm text-raven-muted">
            Technical details
          </summary>
          <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs text-raven-muted">
            {detail}
          </pre>
        </details>
      </section>
    </main>
  );
}

function routeErrorDetail(error: unknown): string {
  if (isRouteErrorResponse(error)) {
    return [
      `Status: ${error.status}`,
      `Status text: ${error.statusText}`,
      typeof error.data === "string" ? `Detail: ${error.data}` : null,
    ]
      .filter(Boolean)
      .join("\n");
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown page rendering error.";
}
