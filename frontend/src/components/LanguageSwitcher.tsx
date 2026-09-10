import { Languages } from "lucide-react";

import { useI18n } from "../lib/i18n";

export function LanguageSwitcher({ compact = false }: { compact?: boolean }): JSX.Element {
  const { language, setLanguage, t } = useI18n();
  return (
    <label className="inline-flex min-w-0 items-center gap-2 text-xs text-raven-muted">
      <Languages className="h-4 w-4 flex-none" aria-hidden="true" />
      <span className={compact ? "sr-only" : "whitespace-nowrap"}>{t("Language")}</span>
      <select
        value={language}
        onChange={(event) => setLanguage(event.target.value === "es" ? "es" : "en")}
        aria-label={t("Language")}
        className="min-w-0 rounded border border-raven-border bg-raven-panelSoft px-2 py-1.5 text-xs text-raven-text outline-none focus:border-raven-violet"
      >
        <option value="en">English</option>
        <option value="es">Español</option>
      </select>
    </label>
  );
}
