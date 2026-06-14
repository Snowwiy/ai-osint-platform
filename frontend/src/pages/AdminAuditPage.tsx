import { ChevronDown, ChevronRight, RefreshCw, Search } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { LongValue } from "../components/LongValue";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { listAuditEvents } from "../lib/api";
import { useAuth } from "../lib/useAuth";
import type { AuditLogEntry, AuditLogFilters } from "../types";

interface AuditFilterForm {
  action: string;
  resourceType: string;
  actorId: string;
  investigationId: string;
  startDate: string;
  endDate: string;
}

const initialForm: AuditFilterForm = {
  action: "",
  resourceType: "",
  actorId: "",
  investigationId: "",
  startDate: "",
  endDate: "",
};

export function AdminAuditPage(): JSX.Element {
  const { user } = useAuth();
  const [form, setForm] = useState<AuditFilterForm>(initialForm);
  const [filters, setFilters] = useState<AuditLogFilters>({
    limit: 50,
    offset: 0,
  });
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filterError, setFilterError] = useState<string | null>(null);

  const audit = useQuery({
    queryKey: ["admin-audit", filters],
    queryFn: () => listAuditEvents(filters),
    enabled: user?.role === "admin",
  });

  if (user?.role !== "admin") {
    return (
      <>
        <PageHeader title="Audit" eyebrow="Admin only" />
        <ErrorBlock message="You need an administrator account to view audit logs." />
      </>
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const actorId = optionalText(form.actorId);
    const investigationId = optionalText(form.investigationId);
    if (actorId && !isUuid(actorId)) {
      setFilterError("Actor ID must be a valid UUID.");
      return;
    }
    if (investigationId && !isUuid(investigationId)) {
      setFilterError("Investigation ID must be a valid UUID.");
      return;
    }
    setFilterError(null);
    setFilters({
      action: optionalText(form.action),
      resource_type: optionalText(form.resourceType),
      actor_id: actorId,
      investigation_id: investigationId,
      start_date: toIsoDateTime(form.startDate),
      end_date: toIsoDateTime(form.endDate),
      limit: 50,
      offset: 0,
    });
  }

  return (
    <>
      <PageHeader title="Audit Log" eyebrow="Security operations" />

      <form
        onSubmit={handleSubmit}
        className="mb-6 rounded-lg border border-raven-border bg-raven-panel/85 p-4"
      >
        <div className="grid gap-3 md:grid-cols-3">
          <AuditInput
            label="Action"
            value={form.action}
            onChange={(value) => setForm({ ...form, action: value })}
            placeholder="recon.executed"
          />
          <AuditInput
            label="Resource"
            value={form.resourceType}
            onChange={(value) => setForm({ ...form, resourceType: value })}
            placeholder="investigation"
          />
          <AuditInput
            label="Actor ID"
            value={form.actorId}
            onChange={(value) => setForm({ ...form, actorId: value })}
            placeholder="UUID"
          />
          <AuditInput
            label="Investigation ID"
            value={form.investigationId}
            onChange={(value) => setForm({ ...form, investigationId: value })}
            placeholder="UUID"
          />
          <AuditInput
            label="Start"
            type="datetime-local"
            value={form.startDate}
            onChange={(value) => setForm({ ...form, startDate: value })}
          />
          <AuditInput
            label="End"
            type="datetime-local"
            value={form.endDate}
            onChange={(value) => setForm({ ...form, endDate: value })}
          />
        </div>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="submit"
            className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
          >
            <Search className="h-4 w-4" aria-hidden="true" />
            Apply filters
          </button>
          <button
            type="button"
            onClick={() => {
              setForm(initialForm);
              setFilters({ limit: 50, offset: 0 });
              setFilterError(null);
            }}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted hover:text-raven-text"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={() => void audit.refetch()}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted hover:text-raven-text"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        </div>
        {filterError ? (
          <div className="mt-4 rounded-md border border-amber-300/30 bg-amber-400/10 p-3 text-sm text-amber-100">
            {filterError}
          </div>
        ) : null}
      </form>

      {audit.isLoading ? <LoadingBlock label="Loading audit events" /> : null}
      {audit.isError ? <ErrorBlock message={audit.error.message} /> : null}
      {audit.data ? (
        audit.data.items.length ? (
          <div className="overflow-hidden rounded-lg border border-raven-border bg-raven-panel/85">
            <div className="border-b border-raven-border px-4 py-3 text-sm text-raven-muted">
              Showing {audit.data.items.length} of {audit.data.total} events
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-raven-border text-sm">
                <thead className="bg-raven-panelSoft text-left text-xs uppercase tracking-wide text-raven-muted">
                  <tr>
                    <th className="px-4 py-3">Event</th>
                    <th className="px-4 py-3">Actor</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Investigation</th>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Metadata</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-raven-border">
                  {audit.data.items.map((entry) => (
                    <AuditRow
                      key={entry.id}
                      entry={entry}
                      expanded={expandedId === entry.id}
                      onToggle={() =>
                        setExpandedId(expandedId === entry.id ? null : entry.id)
                      }
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <EmptyBlock message="No audit events match the current filters." />
        )
      ) : null}
    </>
  );
}

function AuditInput({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
}): JSX.Element {
  return (
    <label className="text-sm">
      <span className="mb-1 block text-raven-muted">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
      />
    </label>
  );
}

function AuditRow({
  entry,
  expanded,
  onToggle,
}: {
  entry: AuditLogEntry;
  expanded: boolean;
  onToggle: () => void;
}): JSX.Element {
  return (
    <>
      <tr className="align-top">
        <td className="px-4 py-3">
          <p className="font-medium text-raven-text">{entry.action}</p>
          <p className="mt-1 text-xs text-raven-muted">{entry.ip_address ?? "No IP"}</p>
        </td>
        <td className="px-4 py-3 text-raven-muted">
          <LongValue value={entry.actor_id ?? "System"} maxLength={24} />
        </td>
        <td className="px-4 py-3">
          <p className="text-raven-text">{entry.resource_type ?? "unknown"}</p>
          <LongValue
            value={entry.resource_id ?? "No resource ID"}
            className="mt-1 text-xs text-raven-muted"
            maxLength={28}
          />
        </td>
        <td className="px-4 py-3 max-w-64 text-raven-muted">
          <LongValue value={entry.investigation_id ?? "None"} maxLength={28} />
        </td>
        <td className="px-4 py-3 whitespace-nowrap text-raven-muted">
          {formatDate(entry.created_at)}
        </td>
        <td className="px-4 py-3">
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex items-center gap-1 rounded-md border border-raven-border px-2 py-1 text-xs text-raven-muted hover:text-raven-text"
          >
            {expanded ? (
              <ChevronDown className="h-3 w-3" aria-hidden="true" />
            ) : (
              <ChevronRight className="h-3 w-3" aria-hidden="true" />
            )}
            Preview
          </button>
        </td>
      </tr>
      {expanded ? (
        <tr>
          <td colSpan={6} className="bg-raven-bg/60 px-4 py-3">
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-md border border-raven-border bg-black/20 p-3 text-xs leading-5 text-raven-muted">
              {JSON.stringify(entry.metadata, null, 2)}
            </pre>
          </td>
        </tr>
      ) : null}
    </>
  );
}

function optionalText(value: string): string | undefined {
  const clean = value.trim();
  return clean || undefined;
}

function toIsoDateTime(value: string): string | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed.toISOString();
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}
