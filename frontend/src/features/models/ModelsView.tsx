import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { formatPlain } from "../../format";
import { DataTable } from "../../design/DataTable";
import { InvestigationSection } from "../../design/InvestigationSection";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { SeverityChip } from "../../design/SeverityChip";
import { ShapeCurve } from "../../design/ShapeCurve";
import { StateBlock } from "../../design/StateBlock";
import { Badge } from "../../design/ui/Badge";
import { EmptyState } from "../../design/ui/Feedback";
import { MetaList, PageHeader } from "../../design/ui/PageHeader";
import { FieldLabel } from "../../design/ui/Panel";
import { ToggleChips } from "../../design/ui/Segmented";

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
        eyebrow="S6 · #/models"
        title="Model Info"
        description="Calibration identity, conformal ladder capacity, and fitted shapes. Provisional calibration is labelled provisional; held-out coverage is pending measurement."
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
            {models.meta !== null && <ProvenanceHeader meta={models.meta} />}
            <DataTable
              testId="s6-artifacts"
              caption="Registered calibration artifacts"
              columns={[
                {
                  header: "Artifact",
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
                  header: "State",
                  render: (r) => (
                    <span className="flex flex-wrap gap-2">
                      <SeverityChip value={r.loaded ? "PASS" : "INDETERMINATE"} />
                      {r.provisional && <SeverityChip value="DEGRADED" />}
                    </span>
                  ),
                },
                {
                  header: "Card note",
                  secondary: true,
                  render: (r) => <span className="text-caption text-text-2">{r.card_note}</span>,
                },
              ]}
              rows={models.data.artifacts}
              keyOf={(r) => r.name}
            />
            <p className="max-w-prose font-mono text-caption text-text-3">
              {models.data.feature_schema_note}
            </p>
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
          <InvestigationSection index="C" title="Conformal ladder capacity" testId="s6-coverage-table">
            <p className="max-w-prose text-body text-text-2">
              Method <span className="font-mono text-text-num">{coverage.data.method}</span> on{" "}
              <span className="font-mono text-text-num">{coverage.data.score}</span>. Measured
              coverage is <span className="text-text-num">pending T-402/T-406</span> (single
              test-split scoring) — capacity below is ladder attainability, not a coverage
              claim.
            </p>
            <DataTable
              testId="s6-coverage-rows"
              caption="Per-group ladder capacity"
              columns={[
                {
                  header: "Group",
                  rowHeader: true,
                  sortValue: (r) => r.group,
                  render: (r) => <span className="font-mono text-text-num">{r.group}</span>,
                },
                {
                  header: "n_cal",
                  numeric: true,
                  sortValue: (r) => r.n_cal,
                  render: (r) => String(r.n_cal),
                },
                { header: "α", numeric: true, render: (r) => formatPlain(r.alpha, 3) },
                {
                  header: "Attainable α",
                  numeric: true,
                  render: (r) => (r.attainable_alpha !== null ? formatPlain(r.attainable_alpha, 4) : "—"),
                },
                {
                  header: "α supported",
                  render: (r) => <SeverityChip value={r.alpha_supported ? "PASS" : "FAIL"} />,
                },
                {
                  header: "Measured",
                  render: (r) => (
                    <Badge tone="outline" className="cursor-help">
                      <span title={r.measured_coverage_note}>pending</span>
                    </Badge>
                  ),
                },
              ]}
              rows={coverage.data.groups}
              keyOf={(r) => r.group}
            />
            <div className="space-y-2">
              <FieldLabel>Inspect fitted shape</FieldLabel>
              <ToggleChips
                label="Calibration group"
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
