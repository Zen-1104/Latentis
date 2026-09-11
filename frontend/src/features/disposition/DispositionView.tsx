import { useApi } from "../../hooks/useApi";
import type { InvestigationData } from "../../api/generated/client";
import { InvestigationSection } from "../../design/InvestigationSection";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { StateBlock } from "../../design/StateBlock";
import { Badge } from "../../design/ui/Badge";
import { Button } from "../../design/ui/Button";
import { EmptyState } from "../../design/ui/Feedback";
import { PageHeader } from "../../design/ui/PageHeader";
import { TechnicalDetails } from "../../design/ui/Disclosure";
import { SURFACE_COPY } from "../../design/vocabulary";
import { navigate } from "../../router";
import { DispositionPanel } from "./DispositionPanel";
import { ReportPanel } from "./ReportPanel";

/** S8 Disposition & Report for one component. */
export function DispositionView({ componentId }: { componentId: string }): React.JSX.Element {
  const inv = useApi<InvestigationData>(
    `/components/${encodeURIComponent(componentId)}/investigation`,
    { timeoutMs: 60000 },
  );
  return (
    <div className="space-y-6">
      <PageHeader
        question={SURFACE_COPY.S8?.question ?? ""}
        crumbs={[
          { label: "Mission Control", to: { surface: "S1" } },
          { label: componentId, to: { surface: "S3", componentId } },
          { label: "Decision" },
        ]}
        eyebrow={`S8 · #/components/${componentId}/dispose`}
        title="Disposition & Report"
        description={SURFACE_COPY.S8?.summary ?? ""}
        badges={<Badge tone="neutral">{componentId}</Badge>}
        actions={
          <Button variant="secondary" onClick={() => navigate({ surface: "S3", componentId })}>
            ← Back to investigation
          </Button>
        }
      />
      <StateBlock
        status={inv.status}
        error={inv.error}
        onRetry={inv.retry}
        testId="s8-inv"
        skeletonRows={5}
        empty={
          <EmptyState
            title="Unknown component or no dataset ingested"
            description="A disposition can only be recorded against a part in the active dataset."
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
            <InvestigationSection
              index="1"
              title="Record your decision"
              hint="LATENTIS recommends; you decide. The record is append-only and captures the exact system output alongside it."
              testId="s8-decision"
            >
              <DispositionPanel
                componentId={componentId}
                recommendation={inv.data.recommendation?.action ?? "—"}
                trigger={inv.data.recommendation?.trigger ?? ""}
              />
            </InvestigationSection>
            <InvestigationSection
              index="2"
              title="Produce the report"
              hint="A self-contained document carrying the evidence, the calculation history and the synthetic-data marking."
              testId="s8-report"
            >
              <ReportPanel defaultScope="component" defaultTarget={componentId} />
            </InvestigationSection>
          </>
        )}
      </StateBlock>
    </div>
  );
}
