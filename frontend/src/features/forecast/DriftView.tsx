import { useApi } from "../../hooks/useApi";
import type { InvestigationData } from "../../api/generated/client";
import { InvestigationSection } from "../../design/InvestigationSection";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { StatusBadge } from "../../design/ui/StatusBadge";
import { ShapeCurve } from "../../design/ShapeCurve";
import { StateBlock } from "../../design/StateBlock";
import { formatPlain } from "../../format";
import { Badge } from "../../design/ui/Badge";
import { Button } from "../../design/ui/Button";
import { EmptyState } from "../../design/ui/Feedback";
import { MetaList, PageHeader } from "../../design/ui/PageHeader";
import { TechnicalDetails } from "../../design/ui/Disclosure";
import { SURFACE_COPY } from "../../design/vocabulary";
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
        question={SURFACE_COPY.S4?.question ?? ""}
        crumbs={[
          { label: "Mission Control", to: { surface: "S1" } },
          { label: componentId, to: { surface: "S3", componentId } },
          { label: "Outlook" },
        ]}
        eyebrow={`S4 · #/components/${componentId}/drift`}
        title="Where is this component heading?"
        description={SURFACE_COPY.S4?.summary ?? ""}
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
            {inv.meta !== null && (
              <TechnicalDetails
                label="Data & calculation history"
                hint="dataset, screening profile and model versions"
              >
                <ProvenanceHeader meta={inv.meta} />
              </TechnicalDetails>
            )}
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
              title="What shape does this kind of part usually follow?"
              hint="Learned from many lots of the same part type. The projection is this shape scaled to this component's own early readings — it is not fitted to one part alone."
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
                          { label: "part type / measurement", value: shape.data.group },
                          { label: "curve family", value: shape.data.family },
                          {
                            label: "share of change by 168 h",
                            value: formatPlain(shape.data.phi_168, 4),
                          },
                          { label: "learned from", value: `${shape.data.fitted_on_lots} lots` },
                        ]}
                      />
                      {shape.data.warning !== null && <StatusBadge value="DEGRADED" withHelp />}
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

