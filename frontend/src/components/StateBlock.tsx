import { AlertTriangle, Loader2, SearchX } from "lucide-react";

export function LoadingBlock({ label = "Loading" }: { label?: string }): JSX.Element {
  return (
    <div className="flex min-h-40 items-center justify-center rounded-lg border border-raven-border bg-raven-panel/80 text-raven-muted">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBlock({ message }: { message: string }): JSX.Element {
  return (
    <div className="rounded-lg border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">
      <div className="flex items-center gap-2 font-medium">
        <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        <span>Unable to load data</span>
      </div>
      <p className="mt-2 text-rose-100/80">{message}</p>
    </div>
  );
}

export function EmptyBlock({ message }: { message: string }): JSX.Element {
  return (
    <div className="rounded-lg border border-dashed border-raven-border bg-raven-panel/60 p-8 text-center text-sm text-raven-muted">
      <SearchX className="mx-auto mb-3 h-5 w-5 text-raven-muted" aria-hidden="true" />
      {message}
    </div>
  );
}

