import {
  Archive,
  Building2,
  FileLock2,
  Flag,
  RefreshCw,
  Save,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  getAdminOverview,
  getAdminRetention,
  getAdminSettings,
  getRegistrationPolicy,
  updateAdminFeatureFlags,
  updateAdminRetention,
  updateAdminSettings,
} from "../lib/api";
import { useAuth } from "../lib/useAuth";
import type {
  AdminSettingsResponse,
  FeatureFlagSettings,
  RegistrationPolicyResponse,
  RetentionPolicy,
  RetentionSettings,
} from "../types";

const retentionOptions: Array<{ value: RetentionPolicy; label: string }> = [
  { value: "indefinite", label: "Retain indefinitely" },
  { value: "30_days", label: "Retain for 30 days" },
  { value: "90_days", label: "Retain for 90 days" },
  { value: "180_days", label: "Retain for 180 days" },
  { value: "365_days", label: "Retain for 365 days" },
  { value: "archive_only", label: "Archive only" },
];

const featureLabels: Record<keyof FeatureFlagSettings, string> = {
  enable_ai_analysis: "AI analysis",
  enable_report_exports: "Report exports",
  enable_playbooks: "Defensive playbooks",
  enable_bulk_actions: "Bulk investigation actions",
  enable_collaboration: "Case collaboration",
  enable_audit_exports: "Audit exports",
  enable_advanced_dashboard: "Advanced operations dashboard",
  enable_demo_mode: "Defensive demo mode",
};

export function AdminSettingsPage(): JSX.Element {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<AdminSettingsResponse | null>(null);
  const [retentionDraft, setRetentionDraft] =
    useState<RetentionSettings | null>(null);
  const [flagsDraft, setFlagsDraft] = useState<FeatureFlagSettings | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);

  const settings = useQuery({
    queryKey: ["admin-settings"],
    queryFn: getAdminSettings,
    enabled: user?.role === "admin",
  });
  const retention = useQuery({
    queryKey: ["admin-retention"],
    queryFn: getAdminRetention,
    enabled: user?.role === "admin",
  });
  const overview = useQuery({
    queryKey: ["admin-overview"],
    queryFn: getAdminOverview,
    enabled: user?.role === "admin",
  });
  const registrationPolicy = useQuery({
    queryKey: ["registration-policy", "admin-settings"],
    queryFn: getRegistrationPolicy,
    enabled: user?.role === "admin",
  });

  useEffect(() => {
    if (settings.data) {
      setDraft(settings.data);
      setFlagsDraft(settings.data.feature_flags);
    }
  }, [settings.data]);

  useEffect(() => {
    if (retention.data) {
      setRetentionDraft(retention.data.retention);
    }
  }, [retention.data]);

  const settingsMutation = useMutation({
    mutationFn: () => {
      if (!draft) {
        throw new Error("Settings are not loaded.");
      }
      return updateAdminSettings({
        general: draft.general,
        security: draft.security,
        export_controls: draft.export_controls,
        report_branding: draft.report_branding,
        audit_policy: draft.audit_policy,
      });
    },
    onSuccess: async (data) => {
      setDraft(data);
      setToast({ kind: "success", message: "Admin settings saved." });
      await refreshGovernanceQueries(queryClient);
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });

  const flagsMutation = useMutation({
    mutationFn: () => {
      if (!flagsDraft) {
        throw new Error("Feature flags are not loaded.");
      }
      return updateAdminFeatureFlags(flagsDraft);
    },
    onSuccess: async (data) => {
      setFlagsDraft(data.feature_flags);
      setToast({ kind: "success", message: "Feature flags updated." });
      await refreshGovernanceQueries(queryClient);
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });

  const retentionMutation = useMutation({
    mutationFn: () => {
      if (!retentionDraft) {
        throw new Error("Retention policies are not loaded.");
      }
      return updateAdminRetention(retentionDraft);
    },
    onSuccess: async (data) => {
      setRetentionDraft(data.retention);
      setToast({ kind: "success", message: "Retention policies updated." });
      await refreshGovernanceQueries(queryClient);
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });

  if (user?.role !== "admin") {
    return (
      <>
        <PageHeader title="Admin Settings" eyebrow="Admin only" />
        <ErrorBlock message="Administrator access is required." />
      </>
    );
  }

  if (settings.isLoading || retention.isLoading || overview.isLoading) {
    return <LoadingBlock label="Loading governance settings" />;
  }
  const error = settings.error ?? retention.error ?? overview.error;
  if (error) {
    return <ErrorBlock message={error} />;
  }
  if (!draft || !retentionDraft || !flagsDraft) {
    return <EmptyBlock message="Governance settings are unavailable." />;
  }

  const eligible = retention.data?.eligible_for_archive ?? {};
  const isSaving =
    settingsMutation.isPending ||
    flagsMutation.isPending ||
    retentionMutation.isPending;

  return (
    <>
      <PageHeader
        title="Admin Settings"
        eyebrow="Enterprise governance"
        actions={
          <button
            type="button"
            onClick={() => {
              setToast(null);
              void settings.refetch();
              void retention.refetch();
              void overview.refetch();
            }}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        }
      />
      {toast ? (
        <ToastBanner toast={toast} onDismiss={() => setToast(null)} />
      ) : null}

      {overview.data ? (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Users"
            value={overview.data.total_users}
            icon={<Building2 className="h-5 w-5" />}
          />
          <StatCard
            label="Active investigations"
            value={overview.data.active_investigations}
            icon={<ShieldCheck className="h-5 w-5" />}
          />
          <StatCard
            label="Archived investigations"
            value={overview.data.archived_investigations}
            icon={<Archive className="h-5 w-5" />}
          />
          <StatCard
            label="Reports generated"
            value={overview.data.reports_generated}
            icon={<FileLock2 className="h-5 w-5" />}
          />
          <StatCard
            label="Audit events"
            value={overview.data.audit_events}
            icon={<ShieldCheck className="h-5 w-5" />}
          />
          <StatCard
            label="Report storage"
            value={formatBytes(overview.data.report_storage_bytes)}
            icon={<FileLock2 className="h-5 w-5" />}
          />
          <StatCard
            label="Enabled flags"
            value={overview.data.feature_flags_enabled}
            icon={<Flag className="h-5 w-5" />}
          />
          <StatCard
            label="Retention policies"
            value={overview.data.retention_policies_configured}
            icon={<Archive className="h-5 w-5" />}
          />
        </div>
      ) : null}

      <div className="space-y-6">
        <RegistrationPolicyPanel policy={registrationPolicy.data} />

        <SettingsSection
          icon={Building2}
          title="General"
          description="Internal deployment identity and support context."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <TextField
              label="Platform name"
              value={draft.general.platform_name}
              onChange={(platform_name) =>
                setDraft({
                  ...draft,
                  general: { ...draft.general, platform_name },
                })
              }
            />
            <TextField
              label="Deployeent label"
              value={draft.general.deployment_label}
              onChange={(deployment_label) =>
                setDraft({
                  ...draft,
                  general: { ...draft.general, deployment_label },
                })
              }
            />
            <TextField
              label="Support contact"
              value={draft.general.support_contact}
              onChange={(support_contact) =>
                setDraft({
                  ...draft,
                  general: { ...draft.general, support_contact },
                })
              }
            />
          </div>
        </SettingsSection>

        <SettingsSection
          icon={ShieldCheck}
          title="Security and audit policy"
          description="Operational notices and configurable non-critical audit events."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <TextField
              label="Classification banner"
              value={draft.security.classification_banner}
              onChange={(classification_banner) =>
                setDraft({
                  ...draft,
                  security: { ...draft.security, classification_banner },
                })
              }
            />
            <ToggleField
              label="Require export confirmation"
              checked={draft.security.require_export_confirmation}
              onChange={(require_export_confirmation) =>
                setDraft({
                  ...draft,
                  security: {
                    ...draft.security,
                    require_export_confirmation,
                  },
                })
              }
            />
            <ToggleField
              label="Require engagement for new investigations"
              checked={draft.security.require_engagement_for_new_investigations}
              onChange={(require_engagement_for_new_investigations) =>
                setDraft({
                  ...draft,
                  security: {
                    ...draft.security,
                    require_engagement_for_new_investigations,
                  },
                })
              }
            />
            <ToggleField
              label="Warn on out-of-scope targets"
              checked={draft.security.warn_on_out_of_scope_targets}
              onChange={(warn_on_out_of_scope_targets) =>
                setDraft({
                  ...draft,
                  security: {
                    ...draft.security,
                    warn_on_out_of_scope_targets,
                  },
                })
              }
            />
            <ToggleField
              label="Block out-of-scope targets"
              checked={draft.security.block_out_of_scope_targets}
              onChange={(block_out_of_scope_targets) =>
                setDraft({
                  ...draft,
                  security: {
                    ...draft.security,
                    block_out_of_scope_targets,
                  },
                })
              }
            />
            <ToggleField
              label="Require approved authorization"
              checked={draft.security.require_approved_authorization}
              onChange={(require_approved_authorization) =>
                setDraft({
                  ...draft,
                  security: {
                    ...draft.security,
                    require_approved_authorization,
                  },
                })
              }
            />
          </div>
          <p className="mt-3 text-xs leading-5 text-raven-muted">
            Engagement controls are governance safeguards. The default posture is
            warn-first so existing investigations and demo data remain usable.
          </p>
          <h3 className="mb-3 mt-5 text-sm font-semibold text-raven-text">
            Audit policy
          </h3>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {Object.entries(draft.audit_policy).map(([key, value]) => (
              <ToggleField
                key={key}
                label={humanize(key)}
                checked={value}
                onChange={(checked) =>
                  setDraft({
                    ...draft,
                    audit_policy: {
                      ...draft.audit_policy,
                      [key]: checked,
                    },
                  })
                }
              />
            ))}
          </div>
        </SettingsSection>

        <SettingsSection
          icon={Archive}
          title="Data retention"
          description="Policies mark data as archive-eligible. Destructive deletion is disabled."
        >
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {(
              Object.keys(retentionDraft) as Array<keyof RetentionSettings>
            ).map((key) => (
              <label key={key} className="min-w-0 text-sm text-raven-muted">
                <span className="mb-1 block">{humanize(key)}</span>
                <select
                  value={retentionDraft[key]}
                  onChange={(event) =>
                    setRetentionDraft({
                      ...retentionDraft,
                      [key]: event.target.value as RetentionPolicy,
                    })
                  }
                  className="w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
                >
                  {retentionOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <span className="mt-1 block text-xs">
                  Eligible now: {eligible[key] ?? 0}
                </span>
              </label>
            ))}
          </div>
          <ActionButton
            label="Save retention"
            pending={retentionMutation.isPending}
            onClick={() => retentionMutation.mutate()}
          />
        </SettingsSection>

        <SettingsSection
          icon={FileLock2}
          title="Export controls and report branding"
          description="Controls are enforced during generation and download."
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {Object.entries(draft.export_controls).map(([key, value]) => (
              <ToggleField
                key={key}
                label={humanize(key)}
                checked={value}
                onChange={(checked) =>
                  setDraft({
                    ...draft,
                    export_controls: {
                      ...draft.export_controls,
                      [key]: checked,
                    },
                  })
                }
              />
            ))}
          </div>
          <h3 className="mb-3 mt-5 text-sm font-semibold text-raven-text">
            Report branding
          </h3>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {(
              [
                "coepany_name",
                "report_title_prefix",
                "logo_path",
                "analyst_name",
                "prieary_color",
                "secondary_color",
                "footer_text",
              ] as Array<keyof AdminSettingsResponse["report_branding"]>
            ).map((key) => (
              <TextField
                key={key}
                label={humanize(key)}
                type={key.includes("color") ? "color" : "text"}
                value={draft.report_branding[key]}
                onChange={(value) =>
                  setDraft({
                    ...draft,
                    report_branding: {
                      ...draft.report_branding,
                      [key]: value,
                    },
                  })
                }
              />
            ))}
            <label className="min-w-0 text-sm text-raven-muted">
              <span className="mb-1 block">Confidentiality level</span>
              <select
                value={draft.report_branding.confidentiality_label}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    report_branding: {
                      ...draft.report_branding,
                      confidentiality_label: event.target.value as
                        AdminSettingsResponse["report_branding"]["confidentiality_label"],
                    },
                  })
                }
                className="w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
              >
                <option value="Internal">Internal</option>
                <option value="Client Confidential">Client Confidential</option>
                <option value="Restricted">Restricted</option>
              </select>
            </label>
          </div>
        </SettingsSection>

        <SettingsSection
          icon={Flag}
          title="Feature flags"
          description="Disabled features are hidden in navigation and rejected by the API."
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {(
              Object.keys(flagsDraft) as Array<keyof FeatureFlagSettings>
            ).map((key) => (
              <ToggleField
                key={key}
                label={featureLabels[key]}
                checked={flagsDraft[key]}
                onChange={(checked) =>
                  setFlagsDraft({ ...flagsDraft, [key]: checked })
                }
              />
            ))}
          </div>
          <ActionButton
            label="Save feature flags"
            pending={flagsMutation.isPending}
            onClick={() => flagsMutation.mutate()}
          />
        </SettingsSection>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <ActionButton
          label="Save settings"
          pending={settingsMutation.isPending}
          onClick={() => settingsMutation.mutate()}
        />
        <button
          type="button"
          disabled={isSaving}
          onClick={() => {
            if (settings.data) {
              setDraft(settings.data);
              setFlagsDraft(settings.data.feature_flags);
            }
            if (retention.data) {
              setRetentionDraft(retention.data.retention);
            }
            setToast(null);
          }}
          className="rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted hover:text-raven-text disabled:opacity-50"
        >
          Cancel changes
        </button>
      </div>
    </>
  );
}

function SettingsSection({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof ShieldCheck;
  title: string;
  description: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <section className="min-w-0 overflow-hidden rounded-lg border border-raven-border bg-raven-panel/85 p-4 md:p-5">
      <div className="mb-4 flex min-w-0 items-start gap-3">
        <Icon className="mt-0.5 h-5 w-5 flex-none text-raven-cyan" />
        <div className="min-w-0">
          <h2 className="text-base font-semibold">{title}</h2>
          <p className="mt-1 break-words text-sm text-raven-muted">
            {description}
          </p>
        </div>
      </div>
      {children}
    </section>
  );
}

function RegistrationPolicyPanel({
  policy,
}: {
  policy: RegistrationPolicyResponse | undefined;
}): JSX.Element {
  return (
    <SettingsSection
      icon={ShieldCheck}
      title="Registration policy"
      description="Public registration is controlled by environment settings. Invite-code values are never displayed."
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <PolicyPill
          label="Public registration"
          value={policy?.public_registration_enabled ? "Enabled" : "Disabled"}
          active={policy?.public_registration_enabled === true}
        />
        <PolicyPill
          label="Approval required"
          value={policy?.requires_approval ? "Yes" : "No"}
          active={policy?.requires_approval === true}
        />
        <PolicyPill
          label="Invite code"
          value={policy?.invite_code_required ? "Configured" : "Not configured"}
          active={policy?.invite_code_required === true}
        />
        <PolicyPill
          label="Default role"
          value={policy?.default_role ?? "Analyst"}
          active
        />
      </div>
      <p className="mt-3 text-xs text-raven-muted">
        Use environment variables to change registration behavior:
        PUBLIC_REGISTRATION_ENABLED, REGISTRATION_REQUIRES_APPROVAL,
        REGISTRATION_INVITE_CODE, and DEFAULT_REGISTERED_USER_ROLE.
      </p>
    </SettingsSection>
  );
}

function PolicyPill({
  label,
  value,
  active,
}: {
  label: string;
  value: string;
  active: boolean;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-bg/60 p-3">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
      <p
        className={[
          "mt-1 text-sm font-medium",
          active ? "text-raven-text" : "text-raven-muted",
        ].join(" ")}
      >
        {value}
      </p>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "color";
}): JSX.Element {
  return (
    <label className="min-w-0 text-sm text-raven-muted">
      <span className="mb-1 block">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={[
          "rounded-md border border-raven-border bg-raven-bg text-raven-text",
          type === "color" ? "h-10 w-full p-1" : "w-full px-3 py-2",
        ].join(" ")}
      />
    </label>
  );
}

function ToggleField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}): JSX.Element {
  return (
    <label className="flex min-w-0 items-center justify-between gap-3 rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm">
      <span className="min-w-0 break-words text-raven-text">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 flex-none accent-violet-500"
      />
    </label>
  );
}

function ActionButton({
  label,
  pending,
  onClick,
}: {
  label: string;
  pending: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      className="mt-5 inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
    >
      <Save className="h-4 w-4" aria-hidden="true" />
      {pending ? "Saving..." : label}
    </button>
  );
}

async function refreshGovernanceQueries(
  queryClient: ReturnType<typeof useQueryClient>,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["admin-settings"] }),
    queryClient.invalidateQueries({ queryKey: ["admin-retention"] }),
    queryClient.invalidateQueries({ queryKey: ["admin-overview"] }),
    queryClient.invalidateQueries({ queryKey: ["feature-availability"] }),
  ]);
}

function humanize(value: string): string {
  return value
    .replace(/^audit_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character: string) => character.toUpperCase());
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
