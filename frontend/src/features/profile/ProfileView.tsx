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
        eyebrow="S5 · #/profiles"
        title="Screening Profile"
        description="Limits, k, α, margin reserve and PDA — the configuration, versioned and immutable once referenced. Read-only in this slice; new versions are an explicit engineering action outside the demo path."
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
            title="Mission Risk Posture (active)"
            hint="The policy inputs in force for every verdict in this session."
            testId="s5-active"
          >
            <ValueGrid label="Mission risk posture" values={posture.data.mission_risk_posture} />
            <ValueGrid label="Risk weights" values={posture.data.risk_weights} />
            <p className="max-w-prose text-caption text-text-3">
              Weights are policy inputs (assumed) — structurally unable to move a part across a
              band boundary (RT-010).
            </p>
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
            {doc.meta !== null && <ProvenanceHeader meta={doc.meta} />}
            <DataTable
              testId="s5-doc-table"
              caption={`Profile document ${selected} (backend values; nested objects expandable)`}
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
            <dt className="truncate font-mono text-caption text-text-3" title={k}>
              {k}
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
