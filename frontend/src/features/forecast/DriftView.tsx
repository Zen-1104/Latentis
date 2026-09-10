import { useApi } from "../../hooks/useApi";
import type { InvestigationData } from "../../api/generated/client";
import { InvestigationSection } from "../../design/InvestigationSection";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { SeverityChip } from "../../design/SeverityChip";
import { ShapeCurve } from "../../design/ShapeCurve";
import { StateBlock } from "../../design/StateBlock";
import { formatPlain } from "../../format";
import { Badge } from "../../design/ui/Badge";
import { Button } from "../../design/ui/Button";
import { EmptyState } from "../../design/ui/Feedback";
import { MetaList, PageHeader } from "../../design/ui/PageHeader";
import { navigate } from "../../router";
import { ForecastSection } from "../investigation/ForecastSection";

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
 * S4 Drift Studio: trajectory, forecast, conformal band, safety slope and
 * the fitted population shape curve — the one number the forecast rests on,
 * published and disputable.
 */
export function DriftView({ componentId }: { componentId: string }): React.JSX.Element {
  const inv = useApi<InvestigationData>(
    `/components/${encodeURIComponent(componentId)}/investigation`,
    { timeoutMs: 60000 },
  );
  const worstParam = inv.data?.worst?.parameter;
  const compType = inv.data?.component.component_type;
  const group = compType !== undefined && worstParam !== undefined ? `${compType}/${worstParam}` : null;
  const shape = useApi<ShapePayload>(
    group !== null ? `/models/shape/${encodeURIComponent(group)}` : null,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`S4 · #/components/${componentId}/drift`}
        title="Drift Studio"
        description="Trajectory, forecast, conformal band and safety slope — plus the fitted population shape the forecast rests on, published and disputable."
        badges={<Badge tone="neutral">{componentId}</Badge>}
        actions={
          <Button
            variant="secondary"
            onClick={() => navigate({ surface: "S3", componentId })}
          >
            Full investigation →
          </Button>
        }
      />
      <StateBlock
        status={inv.status}
        error={inv.error}
        onRetry={inv.retry}
        testId="s4-inv"
        skeletonRows={6}
        empty={
          <EmptyState
            title="Unknown component or no dataset ingested"
            description="This component id is not present in the active dataset."
            action={
              <Button variant="primary" onClick={() => navigate({ surface: "S1" })}>
                Back to Mission Control
              </Button>
            }
          />
        }
      >
        {inv.data !== null && (
          <>
            {inv.meta !== null && <ProvenanceHeader meta={inv.meta} />}
            {(inv.data.parameters ?? []).map((p) => (
              <ForecastSection
                key={p.parameter}
                param={p}
                horizon={168}
                testId={`s4-forecast-${p.parameter}`}
                index={p.parameter === worstParam ? "★" : "·"}
              />
            ))}
            <InvestigationSection
              index="Φ"
              title="Fitted population shape"
              hint="One curve per calibration group, fitted across lots. The forecast is this shape scaled to the part."
              testId="s4-shape"
            >
              <StateBlock
                status={shape.status}
                error={shape.error}
                onRetry={shape.retry}
                testId="s4-shape-inner"
                empty={
                  <EmptyState
                    title={`No fitted shape for ${group ?? "this group"}`}
                    description="The model registry has no shape artifact for this calibration group yet."
                  />
                }
              >
                {shape.data !== null && (
                  <>
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
                      <MetaList
                        items={[
                          { label: "group", value: shape.data.group },
                          { label: "family", value: shape.data.family },
                          { label: "Φ(168)", value: formatPlain(shape.data.phi_168, 4) },
                          { label: "fitted on", value: `${shape.data.fitted_on_lots} lots` },
                          { label: "normalisation", value: shape.data.normalisation },
                        ]}
                      />
                      {shape.data.warning !== null && <SeverityChip value="DEGRADED" />}
                    </div>
                    <ShapeCurve points={shape.data.points} testId="s4-shape-chart" />
                  </>
                )}
              </StateBlock>
            </InvestigationSection>
          </>
        )}
      </StateBlock>
    </div>
  );
}

