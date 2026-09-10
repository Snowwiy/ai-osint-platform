import type { ReactNode } from "react";
import { useI18n } from "../lib/i18n";

export function PageHeader({
  title,
  eyebrow,
  actions,
}: {
  title: string;
  eyebrow?: string;
  actions?: ReactNode;
}): JSX.Element {
  const { t } = useI18n();
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        {eyebrow ? (
          <p className="text-xs uppercase tracking-wide text-raven-cyan">{t(eyebrow)}</p>
        ) : null}
        <h1 className="mt-1 text-2xl font-semibold text-raven-text md:text-3xl">
          {t(title)}
        </h1>
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}
