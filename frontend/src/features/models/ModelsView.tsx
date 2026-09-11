import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { formatPlain } from "../../format";
import { DataTable } from "../../design/DataTable";
import { InvestigationSection } from "../../design/InvestigationSection";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { ShapeCurve } from "../../design/ShapeCurve";
import { StateBlock } from "../../design/StateBlock";
import { Badge } from "../../design/ui/Badge";
import { EmptyState, Notice } from "../../design/ui/Feedback";
import { MetaList, PageHeader } from "../../design/ui/PageHeader";
import { FieldLabel } from "../../design/ui/Panel";
import { ToggleChips } from "../../design/ui/Segmented";
import { StatusBadge } from "../../design/ui/StatusBadge";
import { SectionHeader, TechnicalDetails } from "../../design/ui/Disclosure";
import { CONCEPTS, SURFACE_COPY, methodLabel } from "../../design/vocabulary";

interface ModelsPayload {
  artifacts: Array<{
    name: string;
    version: string;
    loaded: boolean;
    provisional: boolean;
    card: string | null;
    card_note: string;
  }>;
  manifest: Record<string, unknown>;
  feature_schema_note: string;
}

interface CoveragePayload {
  groups: Array<{
    group: string;
    n_cal: number;
    alpha: number;
    coverage_target: number;
    attainable_alpha: number | null;
    alpha_supported: boolean;
    measured_coverage: number | null;
    measured_coverage_note: string;
  }>;
  method: string;
  score: string;
}

interface ShapePayload {
  group: string;
  family: string;
  family_param: number;
  phi_168: number;
  fitted_on_lots: number;
  points: Array<{ t_hours: number; phi: number }>;
  normalisation: string;
  warning: string | null;
}

/**
 * S6 Model Info: provisional calibration identity, ladder capacity per
 * group, fitted shape curves. Measured coverage is pending T-402 — the UI
 * says so instead of estimating it.
 */
export function ModelsView(): React.JSX.Element {
  const models = useApi<ModelsPayload>("/models");
  const coverage = useApi<CoveragePayload>("/models/coverage");
  const [group, setGroup] = useState<string | null>(null);
  const shape = useApi<ShapePayload>(
    group !== null ? `/models/shape/${encodeURIComponent(group)}` : null,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        question={SURFACE_COPY.S6?.question ?? ""}
        crumbs={[
          { label: "Mission Control", to: { surface: "S1" } },
          { label: "Analysis methods" },
        ]}
        eyebrow="S6 · #/models"
        title="Model Info"
        description={SURFACE_COPY.S6?.summary ?? ""}
      />

      <StateBlock
        status={models.status}
        error={models.error}
        onRetry={models.retry}
        testId="s6-models"
        empty={
          <EmptyState
            title="Model registry unavailable"
            description="The backend answered but reported no registered calibration artifacts."
          />
        }
      >
        {models.data !== null && (
          <>
            {models.meta !== null && (
              <TechnicalDetails
                label="Data & calculation history"
                hint="dataset, screening profile and model versions"
              >
                <ProvenanceHeader meta={models.meta} />
              </TechnicalDetails>
            )}
            <SectionHeader
              title="Methods in use"
              hint="What each model contributes, and whether it is ready."
              size="sm"
            />
            <ModelCards artifacts={models.data.artifacts} />
            <DataTable
              testId="s6-artifacts"
              caption="The same models, as a table"
              columns={[
                {
                  header: "Model",
                  rowHeader: true,
                  sortValue: (r) => r.name,
                  render: (r) => <span className="font-mono text-text-num">{r.name}</span>,
                },
                {
                  header: "Version",
                  sortValue: (r) => r.version,
                  render: (r) => <span className="font-mono text-text-2">{r.version}</span>,
                },
                {
                  header: "Ready to use?",
                  render: (r) => (
                    <span className="flex flex-wrap gap-2">
                      <StatusBadge value={r.loaded ? "PASS" : "INDETERMINATE"} withHelp />
                      {r.provisional && <StatusBadge value="DEGRADED" withHelp />}
                    </span>
                  ),
                },
                {
                  header: "What it does",
                  secondary: true,
                  render: (r) => <span className="text-caption text-text-2">{r.card_note}</span>,
                },
              ]}
              rows={models.data.artifacts}
              keyOf={(r) => r.name}
            />
            <TechnicalDetails label="Input restrictions" hint="what these models may not see">
              <p className="max-w-prose font-mono text-caption text-text-3">
                {models.data.feature_schema_note}
              </p>
            </TechnicalDetails>
          </>
        )}
      </StateBlock>

      <StateBlock
        status={coverage.status}
        error={coverage.error}
        onRetry={coverage.retry}
        testId="s6-coverage"
        empty={
          <EmptyState
            title="Coverage unavailable"
            description="No per-group ladder capacity was returned for the active calibration."
          />
        }
      >
        {coverage.data !== null && (
          <InvestigationSection
            index="C"
            title="Can each group support the requested confidence?"
            hint="Whether enough reference data exists to calibrate a prediction range. This is availability, not a measured accuracy claim."
            testId="s6-coverage-table"
          >
            <p className="max-w-prose text-body text-text-2">
              Calibrated by{" "}
              <span className="text-text-num">{methodLabel(coverage.data.method)}</span> on{" "}
              <span className="text-text-num">{methodLabel(coverage.data.score)}</span>.
            </p>
            <Notice tone="weak">
              Measured accuracy has not been established yet. The table below shows only whether
              each group has enough reference data to calibrate a range at the requested
              confidence — it is not a statement about how often the range turns out to be
              right.
            </Notice>
            <DataTable
              testId="s6-coverage-rows"
              caption="One row per part type and measurement: whether a prediction range can be calibrated for it"
              columns={[
                {
                  header: "Group",
                  rowHeader: true,
                  sortValue: (r) => r.group,
                  render: (r) => <span className="font-mono text-text-num">{r.group}</span>,
                },
                {
                  header: "Reference points",
                  numeric: true,
                  sortValue: (r) => r.n_cal,
                  render: (r) => String(r.n_cal),
                },
                {
                  header: "Requested confidence",
                  numeric: true,
                  render: (r) => `${formatPlain((1 - r.alpha) * 100, 0)}%`,
                },
                {
                  header: "Best attainable",
                  numeric: true,
                  render: (r) =>
                    r.attainable_alpha !== null
                      ? `${formatPlain((1 - r.attainable_alpha) * 100, 1)}%`
                      : "—",
                },
                {
                  header: "Enough data?",
                  render: (r) => (
                    <StatusBadge value={r.alpha_supported ? "PASS" : "FAIL"} withHelp />
                  ),
                },
                {
                  header: "Measured accuracy",
                  render: (r) => (
                    <Badge tone="outline">
                      <span title={r.measured_coverage_note}>not yet measured</span>
                    </Badge>
                  ),
                },
              ]}
              rows={coverage.data.groups}
              keyOf={(r) => r.group}
            />
            <div className="space-y-2">
              <FieldLabel>Show the learned curve for one group</FieldLabel>
              <ToggleChips
                label="Part type and measurement"
                items={coverage.data.groups.slice(0, 12).map((g) => ({
                  value: g.group,
                  label: g.group,
                  hint: `${g.n_cal} calibration points`,
                }))}
                selected={group === null ? [] : [group]}
                onToggle={(value) => setGroup((prev) => (prev === value ? null : value))}
              />
            </div>
            {group !== null && (
              <StateBlock
                status={shape.status}
                error={shape.error}
                onRetry={shape.retry}
                testId="s6-shape"
                empty={
                  <EmptyState
                    title={`No fitted shape for ${group}`}
                    description="The model registry has no shape artifact for this calibration group yet."
                  />
                }
              >
                {shape.data !== null && (
                  <>
                    <MetaList
                      items={[
                        { label: "family", value: shape.data.family },
                        { label: "Φ(168)", value: formatPlain(shape.data.phi_168, 4) },
                        { label: "fitted on", value: `${shape.data.fitted_on_lots} lots` },
                        { label: "normalisation", value: shape.data.normalisation },
                      ]}
                    />
                    <ShapeCurve points={shape.data.points} testId="s6-shape-curve" />
                  </>
                )}
              </StateBlock>
            )}
          </InvestigationSection>
        )}
      </StateBlock>
    </div>
  );
}

/**
 * One card per model: what it is for in a sentence, then how ready it is.
 *
 * The registry table alone read as a developer artefact list; a reader
 * needs to know what each model contributes before its version string
 * means anything. Purpose text comes from the shared vocabulary where the
 * model is one we have copy for, and from the backend's own card note
 * otherwise — it is never invented.
 */
function ModelCards({
  artifacts,
}: {
  artifacts: ModelsPayload["artifacts"];
}): React.JSX.Element {
  const PURPOSE: Readonly<Record<string, string>> = {
    conformal: CONCEPTS.conformal?.explain ?? "",
    drift_shape: CONCEPTS.drift_shape?.explain ?? "",
  };
  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      {artifacts.map((a) => (
        <div
          key={a.name}
          className="flex min-w-0 flex-col gap-3 rounded-md border border-border-1 bg-surface-1 p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h3 className="text-h2 font-semibold text-text-1">
              {CONCEPTS[a.name]?.label ?? a.name.replace(/_/g, " ")}
            </h3>
            <span className="flex flex-wrap gap-2">
              <StatusBadge value={a.loaded ? "PASS" : "INDETERMINATE"} withHelp />
              {a.provisional && <StatusBadge value="DEGRADED" withHelp />}
            </span>
          </div>
          <p className="max-w-prose text-body text-text-2">
            {PURPOSE[a.name] !== undefined && PURPOSE[a.name] !== ""
              ? PURPOSE[a.name]
              : a.card_note}
          </p>
          {a.provisional && (
            <p className="text-caption text-evidence-weak">
              <span aria-hidden="true">≈</span> Provisional calibration: usable, but its accuracy
              has not been measured on held-out data yet.
            </p>
          )}
          <p className="mt-auto break-all font-mono text-caption text-text-3">
            {a.name} · {a.version}
          </p>
        </div>
      ))}
    </div>
  );
}
