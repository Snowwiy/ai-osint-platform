import { CheckCircle2, X, XCircle } from "lucide-react";

export interface ToastState {
  kind: "success" | "error";
  message: string;
}

export function ToastBanner({
  toast,
  onDismiss,
}: {
  toast: ToastState;
  onDismiss: () => void;
}): JSX.Element {
  const Icon = toast.kind === "success" ? CheckCircle2 : XCircle;
  const colors =
    toast.kind === "success"
      ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100"
      : "border-rose-400/30 bg-rose-500/10 text-rose-100";

  return (
    <div
      className={`mb-5 flex items-start justify-between gap-3 rounded-lg border p-3 text-sm ${colors}`}
      role="status"
    >
      <div className="flex items-start gap-2">
        <Icon className="mt-0.5 h-4 w-4 flex-none" aria-hidden="true" />
        <span>{toast.message}</span>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="rounded p-1 opacity-80 hover:bg-white/10 hover:opacity-100"
        aria-label="Dismiss message"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
