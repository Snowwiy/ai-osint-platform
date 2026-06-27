import { Check, Copy } from "lucide-react";
import { useState } from "react";

interface LongValueProps {
  value: string | null | undefined;
  label?: string;
  secondary?: string | null;
  className?: string;
  maxLength?: number;
}

export function LongValue({
  value,
  label,
  secondary,
  className = "",
  maxLength = 72,
}: LongValueProps): JSX.Element {
  const [copied, setCopied] = useState(false);
  const text = value?.trim() || "None";
  const shouldShorten = text.length > maxLength;
  const display = shouldShorten ? `${text.slice(0, maxLength - 3)}...` : text;

  async function copyValue(): Promise<void> {
    if (!value) {
      return;
    }
    try {
      await window.navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className={["min-w-0", className].join(" ")}>
      {label ? (
        <p className="mb-1 text-xs uppercase tracking-wide text-raven-muted">
          {label}
        </p>
      ) : null}
      <div className="flex min-w-0 items-start gap-2">
        <span
          className="min-w-0 flex-1 whitespace-normal break-all text-raven-text"
          title={text}
        >
          {display}
        </span>
        {value ? (
          <button
            type="button"
            onClick={() => void copyValue()}
            className="inline-flex h-7 w-7 flex-none items-center justify-center rounded-md border border-raven-border text-raven-muted hover:border-raven-violet hover:text-raven-text"
            title="Copy full value"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <Copy className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            <span className="sr-only">Copy full value</span>
          </button>
        ) : null}
      </div>
      {secondary ? (
        <p className="mt-1 whitespace-normal break-all text-xs text-raven-muted">
          {secondary}
        </p>
      ) : null}
    </div>
  );
}
