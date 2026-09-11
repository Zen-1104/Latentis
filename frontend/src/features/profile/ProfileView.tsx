import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { formatPlain } from "../../format";
import { DataTable } from "../../design/DataTable";
import { InvestigationSection } from "../../design/InvestigationSection";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { StateBlock } from "../../design/StateBlock";
import { Badge } from "../../design/ui/Badge";
import { EmptyState } from "../../design/ui/Feedback";
import { PageHeader } from "../../design/ui/PageHeader";
import { FieldLabel } from "../../design/ui/Panel";
import { ToggleChips } from "../../design/ui/Segmented";
import { ValueCell } from "../investigation/ValueCell";
import { MetricCard } from "../../design/ui/Cards";
import { TechnicalDetails } from "../../design/ui/Disclosure";
import { SETTINGS, SURFACE_COPY, settingTerm } from "../../design/vocabulary";
import { formatPlain as fmt } from "../../format";

interface ProfileDoc {
  [k: string]: unknown;
}

interface PosturePayload {
  mission_risk_posture: Record<string, number | string>;
  risk_weights: Record<string, number | string>;
}

/** S5 Screening Profile — read-only for the hackathon slice. */
export function ProfileView({ profileId }: { profileId: string | null }): React.JSX.Element {
  const list = useApi<Array<{ profile_id: string; versions: number[] }>>("/profiles");
  const [selected, setSelected] = useState<string | null>(profileId);
  const doc = useApi<ProfileDoc>(
    selected !== null ? `/profiles/${encodeURIComponent(selected)}` : null,
  );
  const posture = useApi<PosturePayload>("/posture");

  return (
    <div className="space-y-6">
      <PageHeader
        question={SURFACE_COPY.S5?.question ?? ""}
        crumbs={[{ label: "Mission Control", to: { surface: "S1" } }, { label: "Screening rules" }]}
        eyebrow="S5 · #/profiles"
        title="Screening Profile"
        description={SURFACE_COPY.S5?.summary ?? ""}
        badges={<Badge tone="outline">read-only</Badge>}
      />

      <StateBlock
        status={posture.status}
        error={posture.error}
        onRetry={posture.retry}
        testId="s5-posture"
        empty={
          <EmptyState
            title="Posture unavailable"
            description="The backend returned no active mission risk posture."
          />
        }
      >
        {posture.data !== null && (
          <InvestigationSection
            index="α"
            title="The rules in force right now"
            hint="Every verdict in this session is measured against these settings."
            testId="s5-active"
          >
            <SettingsGrid values={posture.data.mission_risk_posture} />
            <TechnicalDetails
              label="How the risk score is weighted"
              hint="ordering only — these cannot change a verdict"
            >
              <ValueGrid label="Risk weights" values={posture.data.risk_weights} />
              <p className="max-w-prose text-caption text-text-3">
                These weights decide the order of the worklist, nothing more. They are
                structurally unable to move a component across a verdict boundary (RT-010).
              </p>
            </TechnicalDetails>
          </InvestigationSection>
        )}
      </StateBlock>

      <StateBlock
        status={list.status}
        error={list.error}
        onRetry={list.retry}
        testId="s5-list"
        empty={<EmptyState title="No profiles" description="No screening profile is registered." />}
      >
        {list.data !== null && (
          <div className="space-y-2">
            <FieldLabel>Profiles</FieldLabel>
            <ToggleChips
              label="Screening profile"
              items={list.data.map((p) => ({
                value: p.profile_id,
                label: (
                  <span className="flex items-center gap-2">
                    <span>{p.profile_id}</span>
                    <span className="text-text-3">v{p.versions.join(", v")}</span>
                  </span>
                ),
                testId: `s5-profile-${p.profile_id}`,
              }))}
              selected={selected === null ? [] : [selected]}
              onToggle={(value) => setSelected((prev) => (prev === value ? null : value))}
            />
          </div>
        )}
      </StateBlock>

      <StateBlock
        status={doc.status}
        error={doc.error}
        onRetry={doc.retry}
        testId="s5-doc"
        empty={
          <EmptyState
            title={selected === null ? "No profile selected" : "No document"}
            description={
              selected === null
                ? "Select a profile above to inspect its versioned document."
                : "This profile has no document body."
            }
          />
        }
      >
        {doc.data !== null && (
          <>
            {doc.meta !== null && (
              <TechnicalDetails
                label="Data & calculation history"
                hint="dataset, screening profile and model versions"
              >
                <ProvenanceHeader meta={doc.meta} />
              </TechnicalDetails>
            )}
            <DataTable
              testId="s5-doc-table"
              caption={`Every field in screening profile ${selected}, exactly as stored`}
              columns={[
                {
                  header: "Field",
                  rowHeader: true,
                  sortValue: (r) => r.k,
                  render: (r) => <span className="font-mono text-text-num">{r.k}</span>,
                },
                {
                  header: "Value",
                  render: (r) =>
                    r.v !== null && typeof r.v === "object" ? (
                      <details className="group">
                        <summary className="inline-flex cursor-pointer list-none items-center gap-2 rounded-sm font-mono text-caption text-text-2 transition-colors duration-fast hover:text-text-1">
                          <span
                            aria-hidden="true"
                            className="transition-transform duration-fast group-open:rotate-90"
                          >
                            ›
                          </span>
                          <span>{"{…}"} expand</span>
                        </summary>
                        <pre className="mt-2 max-h-panel overflow-auto whitespace-pre-wrap rounded-sm border border-border-1 bg-surface-2 p-3 font-mono text-caption text-text-2">
                          {JSON.stringify(r.v, null, 1)}
                        </pre>
                      </details>
                    ) : (
                      <ValueCell name={r.k} value={r.v} />
                    ),
                },
              ]}
              rows={Object.entries(doc.data).map(([k, v]) => ({ k, v }))}
              keyOf={(r) => r.k}
            />
          </>
        )}
      </StateBlock>
    </div>
  );
}

/**
 * The active screening settings, as labelled cards.
 *
 * Replaces the `alpha 0.1000 k 6.0000 margin_fraction 0.2000` strip: each
 * knob gets its human name, a readable value, an explanation on demand and
 * the raw field name for auditors. Percentages and sigma units are applied
 * per-key because the payload reports plain fractions.
 */
function SettingsGrid({
  values,
}: {
  values: Record<string, number | string>;
}): React.JSX.Element {
  const FORMAT: Readonly<Record<string, (v: number) => string>> = {
    alpha: (v) => `${fmt(v * 100, 0)}%`,
    margin_fraction: (v) => `${fmt(v * 100, 0)}%`,
    pda_limit_pct: (v) => `${fmt(v, 1)}%`,
    k: (v) => `${fmt(v, 1)} σ`,
    horizon_hours: (v) => `${fmt(v, 0)} h`,
  };
  // Only the documented knobs get a card; anything else the backend adds
  // still appears, under the technical disclosure below.
  const known = Object.keys(SETTINGS).filter((k) => k in values);

  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {known.map((k) => {
          const raw = values[k];
          const term = settingTerm(k);
          const shown =
            typeof raw === "number"
              ? (FORMAT[k]?.(raw) ?? fmt(raw, 4))
              : String(raw ?? "—");
          return (
            <MetricCard
              key={k}
              label={term?.label ?? k}
              value={shown}
              hint={term?.explain}
              settingKey={k}
              technical={`${k} = ${String(raw)}`}
            />
          );
        })}
      </div>
      <p className="max-w-prose text-caption text-text-3">
        These are configuration, not measurements. Once a screening profile has been referenced
        by a decision it is immutable, so a recorded verdict can always be re-read against the
        exact rules that produced it.
      </p>
    </>
  );
}

/**
 * Key/value grid for a flat config block. A definition list rather than a
 * run of inline spans, so the pairs survive a narrow viewport and read as
 * pairs to a screen reader.
 */
function ValueGrid({
  label,
  values,
}: {
  label: string;
  values: Record<string, number | string>;
}): React.JSX.Element {
  return (
    <section aria-label={label} className="space-y-2">
      <FieldLabel>{label}</FieldLabel>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-4">
        {Object.entries(values).map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="truncate text-caption text-text-3" title={k}>
              {settingTerm(k)?.label ?? k.replace(/_/g, " ")}
            </dt>
            <dd
              className="mt-1 font-mono text-num text-text-num tnum"
              data-tabular-nums="true"
            >
              {typeof v === "number" ? formatPlain(v, 4) : String(v)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
