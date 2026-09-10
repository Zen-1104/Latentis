import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../../api/client";
import type {
  InvestigationData,
  ParameterEvidence,
} from "../../api/generated/client";
import { useApi } from "../../hooks/useApi";
import { navigate } from "../../router";
import { isTraced, formatPlain } from "../../format";
import { CohortStrip, type StripMember } from "../../design/CohortStrip";
import { DataTable } from "../../design/DataTable";
import { FormulaPanel } from "../../design/FormulaPanel";
import { GuardBanner } from "../../design/GuardBanner";
import { InvestigationSection } from "../../design/InvestigationSection";
import { Metric } from "../../design/Metric";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { RiskBreakdown } from "../../design/RiskBreakdown";
import { SeverityChip } from "../../design/SeverityChip";
import { StateBlock } from "../../design/StateBlock";
import { VerdictCard } from "../../design/VerdictCard";
import { Badge } from "../../design/ui/Badge";
import { Button } from "../../design/ui/Button";
import { EmptyState } from "../../design/ui/Feedback";
import { MetaList, PageHeader } from "../../design/ui/PageHeader";
import { FieldLabel } from "../../design/ui/Panel";
import { Tabs, TabPanel } from "../../design/ui/Tabs";
import { EvidenceTable } from "./EvidenceTable";
import { ForecastSection } from "./ForecastSection";
import { DispositionPanel } from "../disposition/DispositionPanel";

interface DistributionMembers {
  parameters: Array<{ parameter: string; members: StripMember[] }>;
}

/**
 * S3 Component Investigation — the flagship forensic workspace.
 * Header → verdict strip → WHY → per-parameter evidence → risk →
 * recommendation → engineer decision → provenance.
 */
export function Investigation({ componentId }: { componentId: string }): React.JSX.Element {
  const inv = useApi<InvestigationData>(
    `/components/${encodeURIComponent(componentId)}/investigation`,
    { timeoutMs: 60000 },
  );
  const [members, setMembers] = useState<DistributionMembers | null>(null);

  useEffect(() => {
    const lotId = inv.data?.component.lot_id;
    if (inv.status !== "ready" || lotId === undefined) return;
    let cancelled = false;
    apiGet<DistributionMembers>(`/lots/${encodeURIComponent(lotId)}/distribution`)
      .then((res) => {
        if (!cancelled) setMembers(res.data);
      })
      .catch(() => {
        if (!cancelled) setMembers({ parameters: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [inv.status, inv.data]);

  return (
    <div className="space-y-6">
      <StateBlock
        status={inv.status}
        error={inv.error}
        onRetry={inv.retry}
        testId="s3-inv"
        skeletonRows={6}
        empty={
          <EmptyState
            title="Unknown component or no dataset ingested"
            description="This component id is not present in the active dataset. Pick a part from its lot, or ingest a screening corpus first."
            action={
              <Button variant="primary" onClick={() => navigate({ surface: "S1" })}>
                Back to Mission Control
              </Button>
            }
          />
        }
      >
        {inv.data !== null && (
          <InvestigationBody data={inv.data} members={members} meta={inv.meta} />
        )}
      </StateBlock>
    </div>
  );
}

function InvestigationBody({
  data,
  members,
  meta,
}: {
  data: InvestigationData;
  members: DistributionMembers | null;
  meta: ReturnType<typeof useApi<InvestigationData>>["meta"];
}): React.JSX.Element {
  const params = useMemo(() => orderParams(data), [data]);
  const [active, setActive] = useState<string | null>(null);
  const worst = data.worst;
  // The server declares the worst parameter; it is the default selection and
  // is never re-ranked in the browser.
  const activeParameter = active ?? worst?.parameter ?? params[0]?.parameter ?? "";
  const current = params.find((p) => p.parameter === activeParameter) ?? params[0];
  const worstBlock = params.find((p) => p.parameter === worst?.parameter);

  const identity: Array<{ label: string; value: React.ReactNode }> = [
    {
      label: "lot",
      value: (
        <button
          type="button"
          onClick={() => navigate({ surface: "S2", lotId: data.component.lot_id })}
          className="rounded-sm underline decoration-border-2 decoration-dotted underline-offset-4 transition-colors duration-fast hover:decoration-text-num"
        >
          {data.component.lot_id}
        </button>
      ),
    },
    { label: "type", value: data.component.component_type },
  ];
  if (data.component.board_id) identity.push({ label: "board", value: data.component.board_id });
  if (data.component.socket_id) identity.push({ label: "socket", value: data.component.socket_id });
  if (data.component.thermal_zone)
    identity.push({ label: "zone", value: data.component.thermal_zone });
  if (data.component.tester_id) identity.push({ label: "tester", value: data.component.tester_id });

  return (
    <>
      <PageHeader
        eyebrow={`S3 · #/components/${data.component.component_id}`}
        title={data.component.component_id}
        monoTitle
        badges={
          <>
            <SeverityChip value={worst?.severity ?? null} testId="s3-worst-severity" />
            <SeverityChip value={worst?.band ?? null} testId="s3-worst-band" />
          </>
        }
        meta={<MetaList items={identity} />}
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => navigate({ surface: "S4", componentId: data.component.component_id })}
              data-testid="s3-goto-drift"
            >
              Drift Studio →
            </Button>
            <Button
              variant="primary"
              onClick={() => navigate({ surface: "S8", componentId: data.component.component_id })}
              data-testid="s3-goto-dispose"
            >
              Record disposition →
            </Button>
          </>
        }
      />

      {meta !== null && <ProvenanceHeader meta={meta} testId="s3-provenance" />}
      <GuardBanner guards={data.guards} scope="component" />

      <InvestigationSection index="V" title="Verdict strip" testId="s3-verdicts">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <VerdictCard
            title="Dynamic PAT (lot-relative)"
            verdict={worstBlock?.dpat?.verdict ?? null}
            testId="s3-verdict-dpat"
          >
            {worstBlock?.dpat?.z !== undefined &&
              worstBlock.dpat.z !== null &&
              isTraced(worstBlock.dpat.z) && (
                <Metric traced={worstBlock.dpat.z} label="robust distance" testId="s3-dpat-z" />
              )}
            <div className="font-mono text-caption text-text-3">
              worst parameter: {worst?.parameter ?? "—"}
            </div>
          </VerdictCard>
          <VerdictCard
            title="Absolute limit"
            verdict={worstBlock?.absolute?.verdict ?? null}
            testId="s3-verdict-absolute"
          >
            {worstBlock?.absolute !== undefined && worstBlock.absolute !== null && (
              <div className="font-mono text-caption text-text-2">
                limit{" "}
                <span className="text-text-num tnum" data-tabular-nums="true">
                  {worstBlock.absolute.limit_high ?? worstBlock.absolute.limit_low ?? "—"}{" "}
                  {worstBlock.absolute.limit_unit}
                </span>
                {worstBlock.absolute.margin_pct !== undefined &&
                  worstBlock.absolute.margin_pct !== null && (
                    <span>
                      {" "}
                      · margin{" "}
                      <span className="text-text-num tnum" data-tabular-nums="true">
                        {formatPlain(worstBlock.absolute.margin_pct * 100, 1)}%
                      </span>
                    </span>
                  )}
              </div>
            )}
          </VerdictCard>
          <VerdictCard
            title="Drift band (forecast)"
            verdict={worst?.band ?? null}
            testId="s3-verdict-band"
          >
            <div className="font-mono text-caption text-text-2">
              recommendation: <span className="text-text-num">{worst?.recommendation ?? "—"}</span>
            </div>
            <div className="font-mono text-caption text-text-3">{worst?.selection_rule ?? ""}</div>
          </VerdictCard>
        </div>
        <p className="max-w-prose text-body text-text-2">
          The three verdicts are shown together on purpose: two of them disagreeing is the
          problem statement rendered as UI. A merged verdict would destroy the evidence.
        </p>
      </InvestigationSection>

      <InvestigationSection index="W" title="Why flagged?" testId="s3-why">
        <WhyNarrative data={data} worstParam={worst?.parameter ?? null} />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-body">
          <WhyLine
            label="Attribution"
            value={worstBlock?.attribution?.verdict ?? null}
            hint="PART means the evidence points at the component, not the setup."
          />
          <WhyLine
            label="System recommendation"
            value={data.recommendation?.action ?? null}
            hint={data.recommendation?.trigger ?? ""}
          />
          <WhyLine
            label="Guarantee"
            value={data.guards?.guarantee_status ?? null}
            hint="VALID means the conformal bound carries its stated coverage."
          />
        </div>
      </InvestigationSection>

      {/* Per-parameter evidence.
          The selector and the evidence chain share one containing block so
          the sticky tab bar stays pinned for the whole (very long) chain —
          nested inside its own panel it would unstick as soon as that panel
          scrolled past, which is a sticky bar that never actually sticks. */}
      <section aria-label="Per-parameter evidence" className="space-y-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="text-h2 font-semibold text-text-1">Per-parameter evidence</h2>
          <Badge tone="outline">{params.length} parameters</Badge>
        </div>
        <p className="max-w-prose text-body text-text-2">
          Server-selected worst parameter first. Choosing a parameter re-scopes every section
          below.
        </p>

        <div className="sticky top-[var(--h-header)] z-nav bg-surface-0 pt-2">
          <Tabs
            label="Parameters"
            items={params.map((p) => ({
              id: p.parameter,
              label: p.parameter,
              note: p.parameter === worst?.parameter ? "worst" : undefined,
              testId: `s3-tab-${p.parameter}`,
            }))}
            activeId={activeParameter}
            onChange={setActive}
            panelId="s3-parameter-panel"
            testIdPrefix="s3-tab-"
          />
        </div>

        {current !== undefined && (
          <TabPanel
            id="s3-parameter-panel"
            labelledBy={`s3-tab-${current.parameter}-tab`}
            className="space-y-6"
          >
            <ParameterEvidenceView
              param={current}
              members={(members?.parameters ?? []).find((m) => m.parameter === current.parameter)?.members ?? null}
              componentId={data.component.component_id}
              horizon={168}
            />
          </TabPanel>
        )}
      </section>

      <InvestigationSection
        index="R"
        title="Risk decomposition"
        hint="Additive contributions that order the worklist. They never decide the band."
        testId="s3-risk"
      >
        <RiskBreakdown risk={data.risk} testId="s3-risk-breakdown" />
      </InvestigationSection>

      <InvestigationSection
        index="D"
        title="Engineer decision"
        hint="The system recommends; the human disposes. An override must carry a reason."
        testId="s3-disposition"
      >
        <DispositionPanel
          componentId={data.component.component_id}
          recommendation={data.recommendation?.action ?? "—"}
          trigger={data.recommendation?.trigger ?? ""}
        />
      </InvestigationSection>

      <InvestigationSection
        index="P"
        title="Provenance"
        hint="Everything needed to recompute the numbers above from this payload alone."
        testId="s3-provenance-detail"
      >
        <ProvenanceDetail data={data} />
      </InvestigationSection>
    </>
  );
}

/** Worst parameter first (server-selected), then payload order. No re-ranking. */
function orderParams(data: InvestigationData): ParameterEvidence[] {
  const params = data.parameters ?? [];
  const worstParam = data.worst?.parameter;
  if (worstParam === undefined) return params;
  return [
    ...params.filter((p) => p.parameter === worstParam),
    ...params.filter((p) => p.parameter !== worstParam),
  ];
}

/**
 * Worst-parameter layers first (backend prose, verbatim), full
 * cross-parameter narrative one disclosure below. Display structuring only:
 * no sentence is written, split, or reordered by the frontend beyond
 * selecting the server-declared worst parameter.
 */
function WhyNarrative({
  data,
  worstParam,
}: {
  data: InvestigationData;
  worstParam: string | null;
}): React.JSX.Element {
  const full =
    typeof data.explanation?.["narrative"] === "string"
      ? (data.explanation["narrative"] as string)
      : null;
  const worstBlock = (data.parameters ?? []).find((p) => p.parameter === worstParam);
  const texts = (worstBlock?.narratives?.texts ?? {}) as Record<string, unknown>;
  const anomaly = typeof texts["anomaly"] === "string" ? (texts["anomaly"] as string) : null;
  const drift = typeof texts["drift"] === "string" ? (texts["drift"] as string) : null;
  return (
    <div className="space-y-2">
      {anomaly !== null && (
        <p data-testid="s3-narrative" className="text-body text-text-1 leading-relaxed max-w-[80ch]">
          {anomaly}
        </p>
      )}
      {drift !== null && (
        <p data-testid="s3-narrative-drift" className="text-body text-text-1 leading-relaxed max-w-[80ch]">
          {drift}
        </p>
      )}
      {anomaly === null && drift === null && (
        <p data-testid="s3-narrative" className="text-body text-text-3">
          No per-parameter narrative was returned for this part.
        </p>
      )}
      {full !== null && (
        <details className="group rounded-sm border border-border-1 bg-surface-2">
          <summary className="flex min-h-control-md cursor-pointer list-none items-center gap-2 px-3 font-mono text-caption text-text-2 transition-colors duration-fast hover:text-text-1">
            <span aria-hidden="true" className="transition-transform duration-fast group-open:rotate-90">
              ›
            </span>
            <span>
              Full cross-parameter narrative ({(data.parameters ?? []).length} parameters, backend
              prose)
            </span>
          </summary>
          <p className="max-w-measure px-3 pb-3 text-body leading-relaxed text-text-2">{full}</p>
        </details>
      )}
    </div>
  );
}

function WhyLine({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | null;
  hint: string;
}): React.JSX.Element {
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-sm border border-border-1 bg-surface-2 p-3">
      <FieldLabel>{label}</FieldLabel>
      <div>
        <SeverityChip value={value} />
      </div>
      {hint !== "" && <p className="text-caption text-text-3">{hint}</p>}
    </div>
  );
}

function ParameterEvidenceView({
  param,
  members,
  componentId,
  horizon,
}: {
  param: ParameterEvidence;
  members: StripMember[] | null;
  componentId: string;
  horizon: number;
}): React.JSX.Element {
  const stats = param.lot_statistics;
  const dpat = param.dpat;
  const notices: string[] = [];
  if (param.fully_traced === false)
    notices.push("ADAPTER VALUES — this parameter ships plain floats for unit-carrying quantities (D-044); marked ≈, never traced.");
  if (stats?.reduced_power === true)
    notices.push("REDUCED POWER — small cohort; MAD path with finite-sample correction.");
  if (param.guards?.insufficient_data === true)
    notices.push("INSUFFICIENT EVIDENCE — required read-point missing; nothing imputed.");

  return (
    <>
      <InvestigationSection
        index="01"
        title={`Measurement & peer evidence · ${param.parameter}`}
        testId="s3-peer"
      >
        <GuardBanner guards={param.guards} notices={notices} scope={param.parameter} />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <VerdictCard title="DPAT" verdict={dpat?.verdict ?? null} testId="s3-param-dpat">
            {dpat?.z !== undefined && dpat.z !== null && isTraced(dpat.z) && (
              <Metric traced={dpat.z} label={`${param.parameter} robust distance`} testId="s3-param-z" />
            )}
            <div className="font-mono text-caption text-text-3">k = {dpat?.k ?? "—"}</div>
          </VerdictCard>
          <VerdictCard title="Absolute" verdict={param.absolute?.verdict ?? null}>
            <div className="font-mono text-caption text-text-2">
              {param.absolute?.limit_high ?? param.absolute?.limit_low ?? "—"} {param.absolute?.limit_unit ?? param.unit}
            </div>
          </VerdictCard>
          <VerdictCard title="Severity" verdict={param.severity ?? null}>
            <div className="font-mono text-caption text-text-3">
              cohort n {param.cohort?.n ?? stats?.n ?? "—"} · {stats?.estimator ?? ""} · {stats?.scope ?? ""}
            </div>
          </VerdictCard>
        </div>

        <DataTable
          testId="s3-readings"
          caption={`Read-points for ${param.parameter} in ${param.unit} (screening-visible only)`}
          columns={[
            { header: "t (h)", numeric: true, render: (r) => String(r.elapsed_hours) },
            {
              header: "Value",
              numeric: true,
              render: (r) =>
                r.value !== undefined && r.value !== null && isTraced(r.value) ? (
                  <Metric traced={r.value} label={`${param.parameter} at ${r.elapsed_hours} h`} />
                ) : (
                  <span className="text-text-3">—</span>
                ),
            },
            { header: "Status", render: (r) => <SeverityChip value={r.status === "OK" ? "PASS" : "INDETERMINATE"} /> },
          ]}
          rows={param.readings ?? []}
          keyOf={(r) => `${r.elapsed_hours}`}
        />

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-caption text-text-2">
          <FieldLabel as="span">Lot baseline</FieldLabel>
          {stats?.median !== undefined && stats.median !== null && isTraced(stats.median) && (
            <Metric traced={stats.median} label="lot median" />
          )}
          {stats?.robust_sigma !== undefined && stats.robust_sigma !== null && isTraced(stats.robust_sigma) && (
            <Metric traced={stats.robust_sigma} label="robust sigma" />
          )}
          {dpat?.limit_high !== undefined && dpat.limit_high !== null && isTraced(dpat.limit_high) && (
            <Metric traced={dpat.limit_high} label="DPAT upper limit" testId="s3-limit-high" />
          )}
          {dpat?.limit_low !== undefined && dpat.limit_low !== null && isTraced(dpat.limit_low) && (
            <Metric traced={dpat.limit_low} label="DPAT lower limit" />
          )}
        </div>
        {dpat?.limit_high !== undefined && dpat.limit_high !== null && isTraced(dpat.limit_high) && (
          <FormulaPanel traced={dpat.limit_high} testId="s3-limit-formula" />
        )}
        {dpat?.z !== undefined && dpat.z !== null && isTraced(dpat.z) && (
          <FormulaPanel traced={dpat.z} testId="s3-z-formula" />
        )}

        {members !== null ? (
          <CohortStrip
            members={members}
            focusId={componentId}
            limitLow={dpat?.limit_low !== undefined && dpat.limit_low !== null && isTraced(dpat.limit_low) ? dpat.limit_low.value : null}
            limitHigh={dpat?.limit_high !== undefined && dpat.limit_high !== null && isTraced(dpat.limit_high) ? dpat.limit_high.value : null}
            median={stats?.median !== undefined && stats.median !== null && isTraced(stats.median) ? stats.median.value : null}
            absHigh={param.absolute?.limit_high ?? null}
            unit={param.unit}
            testId="s3-cohort"
          />
        ) : (
          <p className="text-caption text-text-3">Cohort view unavailable for this lot.</p>
        )}
      </InvestigationSection>

      <InvestigationSection index="02" title={`Attribution · ${param.parameter}`} testId="s3-attribution">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-body text-text-2">Evidence points at</span>
          <AttributionVerdict verdict={param.attribution?.verdict ?? null} />
        </div>
        {param.attribution?.evidence !== undefined && param.attribution.evidence !== null && (
          <EvidenceTable
            record={param.attribution.evidence as Record<string, unknown>}
            testId="s3-attribution-evidence"
            caption="Attribution evidence (backend values)"
          />
        )}
        {param.attribution?.warning !== undefined && param.attribution.warning !== null && (
          <p className="text-body text-text-2 font-mono text-caption">{param.attribution.warning}</p>
        )}
        <EnsembleMembers param={param} />
      </InvestigationSection>

      <ForecastSection param={param} horizon={horizon} testId="s3-forecast" index="03" />

      <InvestigationSection index="04" title={`Data quality & sensor state · ${param.parameter}`} testId="s3-quality">
        <QualityView param={param} />
      </InvestigationSection>

      <InvestigationSection index="05" title={`Explanation layers · ${param.parameter}`} testId="s3-narratives">
        <NarrativesView param={param} />
      </InvestigationSection>
    </>
  );
}

function AttributionVerdict({ verdict }: { verdict: string | null }): React.JSX.Element {
  if (verdict === "PART")
    return (
      <span className="inline-flex items-center gap-2 text-body">
        <SeverityChip value="FAIL" />
        <span className="font-mono text-text-1">PART — the anomaly belongs to the component</span>
      </span>
    );
  if (verdict === "SOCKET" || verdict === "ZONE" || verdict === "TESTER")
    return (
      <span className="inline-flex items-center gap-2 text-body">
        <span className="text-evidence-weak" aria-hidden="true">
          ↻
        </span>
        <span className="font-mono text-text-1">
          {verdict} — setup-attributed; retest recommended, not rejection
        </span>
      </span>
    );
  return <SeverityChip value={verdict} />;
}

function EnsembleMembers({ param }: { param: ParameterEvidence }): React.JSX.Element {
  const m = param.members;
  if (m === undefined || m === null) return <></>;
  const d2 = m.mahalanobis?.d2;
  return (
    <div className="space-y-2">
      <FieldLabel>
        Ensemble · {m.members_fired ?? 0}/{m.members_total ?? 0} members fired
      </FieldLabel>
      <DataTable
        testId="s3-members"
        caption="Per-member positions (max-severity aggregate; disagreement is reported, not averaged)"
        columns={[
          { header: "Member", render: (r) => <span className="font-mono">{r.name}</span> },
          { header: "Verdict", render: (r) => <SeverityChip value={r.verdict} /> },
          { header: "Position", render: (r) => <span className="font-mono">{r.position}</span> },
        ]}
        rows={[
          { name: "DPAT", verdict: m.dpat?.verdict ?? null, position: m.dpat?.position ?? "—" },
          { name: "Tukey", verdict: m.tukey?.verdict ?? null, position: m.tukey?.position ?? "—" },
          {
            name: "Adjusted boxplot",
            verdict: m.adjusted_boxplot?.verdict ?? null,
            position: m.adjusted_boxplot?.position ?? "—",
          },
        ]}
        keyOf={(r) => r.name}
      />
      {d2 !== undefined && d2 !== null && isTraced(d2) && (
        <div className="flex flex-wrap items-center gap-2 text-body">
          <span className="font-mono text-caption text-text-3">Mahalanobis D²</span>
          <Metric traced={d2} label="Mahalanobis D-squared" testId="s3-d2" />
          {m.mahalanobis?.p_value !== undefined && m.mahalanobis.p_value !== null && (
            <span className="font-mono text-caption text-text-3 tnum" data-tabular-nums="true">
              p = {formatPlain(m.mahalanobis.p_value, 4)}
            </span>
          )}
        </div>
      )}
      {(m.mahalanobis?.top_contributions ?? []).length > 0 && (
        <DataTable
          testId="s3-contributions"
          caption="Exact Mahalanobis contribution decomposition (sums to D²)"
          columns={[
            { header: "Parameter", render: (r) => <span className="font-mono">{r.parameter}</span> },
            { header: "Contribution", numeric: true, render: (r) => formatPlain(r.contribution, 3) },
            { header: "Share", numeric: true, render: (r) => `${formatPlain(r.share * 100, 1)}%` },
          ]}
          rows={m.mahalanobis?.top_contributions ?? []}
          keyOf={(r) => r.parameter}
        />
      )}
      {m.cross_check !== undefined && m.cross_check !== null && Object.keys(m.cross_check).length > 0 && (
        <p className="font-mono text-caption text-text-3">
          Advisory cross-check present — displayed for review; it cannot change the verdict.
        </p>
      )}
    </div>
  );
}

function QualityView({ param }: { param: ParameterEvidence }): React.JSX.Element {
  const q = param.quality;
  const cusum = param.cusum;
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div className="space-y-3 rounded-sm border border-border-1 bg-surface-2 p-3">
        <FieldLabel>Measurement quality</FieldLabel>
        {q?.score !== undefined && q.score !== null ? (
          <div>
            <div
              className="font-mono text-num-lg font-semibold text-text-num tnum"
              data-tabular-nums="true"
            >
              {formatPlain(q.score, 3)}
            </div>
            <div className="mt-1 font-mono text-caption text-text-3">
              {q.n_valid}/{q.n_total} valid · {q.n_censored} censored
            </div>
          </div>
        ) : (
          <span className="text-body text-text-3">No quality score returned.</span>
        )}
        {(q?.findings ?? []).length > 0 && (
          <DataTable
            testId="s3-quality-findings"
            caption="Itemised quality deductions"
            columns={[
              { header: "Code", render: (r) => <span className="font-mono">{r.code}</span> },
              { header: "Count", numeric: true, render: (r) => String(r.count) },
              { header: "Detail", render: (r) => r.detail },
              { header: "Action", render: (r) => r.action },
            ]}
            rows={q?.findings ?? []}
            keyOf={(r) => `${r.code}-${r.detail.slice(0, 24)}`}
          />
        )}
        {q?.warning !== undefined && q.warning !== null && (
          <p className="font-mono text-caption text-evidence-weak">
            <span aria-hidden="true">≈</span> {q.warning}
          </p>
        )}
      </div>
      <div className="space-y-3 rounded-sm border border-border-1 bg-surface-2 p-3">
        <FieldLabel>CUSUM persistent-shift evidence (advisory)</FieldLabel>
        {cusum === undefined || cusum === null ? (
          <span className="text-text-3">No CUSUM evidence returned.</span>
        ) : (
          <>
            <div className="flex items-center gap-2">
              {cusum.signal_high === true || cusum.signal_low === true ? (
                <SeverityChip value="ANOMALOUS" />
              ) : (
                <SeverityChip value="PASS" />
              )}
              <span className="font-mono text-caption text-text-2">
                {cusum.n_observations ?? 0} observations · {cusum.n_gaps ?? 0} gaps
              </span>
            </div>
            {cusum.refusal_code !== undefined && cusum.refusal_code !== null && (
              <p className="font-mono text-caption text-evidence-weak">
                <span aria-hidden="true">≈</span> {cusum.refusal_code}
                {cusum.warning !== undefined && cusum.warning !== null ? ` — ${cusum.warning}` : ""}
              </p>
            )}
            <p className="text-caption italic text-text-3">{cusum.advisory_note ?? ""}</p>
          </>
        )}
      </div>
    </div>
  );
}

function NarrativesView({ param }: { param: ParameterEvidence }): React.JSX.Element {
  const narr = param.narratives;
  if (narr === undefined || narr === null) return <span className="text-text-3">No narratives.</span>;
  const texts = narr.texts ?? {};
  const counter = narr.counterfactuals ?? {};
  return (
    <div className="space-y-2">
      {(narr.layers ?? []).map((layer) => {
        const text = (texts as Record<string, unknown>)[layer];
        if (typeof text !== "string" || text === "") return null;
        return (
          <div key={layer} className="rounded-sm border border-border-1 bg-surface-2 p-3">
            <FieldLabel>{layer}</FieldLabel>
            <p className="mt-2 max-w-measure text-body leading-relaxed text-text-1">{text}</p>
          </div>
        );
      })}
      {Object.keys(counter).length > 0 && (
        <EvidenceTable
          record={counter as Record<string, unknown>}
          testId="s3-counterfactuals"
          caption="Counterfactual thresholds — what would change the verdict"
        />
      )}
      {(param.recommendation?.action ?? "") !== "" && (
        <div className="flex flex-wrap items-center gap-2 text-body">
          <span className="font-mono text-caption text-text-3">Parameter recommendation</span>
          <SeverityChip value={param.recommendation?.action ?? null} />
          {param.recommendation?.trigger !== undefined && param.recommendation.trigger !== null && (
            <span className="text-caption text-text-3">{param.recommendation.trigger}</span>
          )}
        </div>
      )}
    </div>
  );
}

function ProvenanceDetail({ data }: { data: InvestigationData }): React.JSX.Element {
  const prov = data.provenance;
  const formulas = prov?.formulas_used ?? [];
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
        {[
          { label: "dataset", value: prov?.dataset_hash ?? "—" },
          { label: "profile", value: prov?.profile_ref ?? "—" },
          { label: "code", value: prov?.code_git_sha ?? "—" },
          { label: "calibration", value: prov?.calibration_dataset ?? "—" },
        ].map((entry) => (
          <div key={entry.label} className="min-w-0">
            <dt className="eyebrow">{entry.label}</dt>
            <dd className="mt-1 break-all font-mono text-caption text-text-num">{entry.value}</dd>
          </div>
        ))}
      </dl>
      <Badge tone="synthetic">data_provenance: {prov?.data_provenance ?? "SYNTHETIC"}</Badge>
      <DataTable
        testId="s3-formulas"
        caption={`Formula registry entries referenced by this payload (${formulas.length})`}
        columns={[
          { header: "formula_id", render: (r) => <span className="font-mono">{r.formula_id}</span> },
          { header: "Expression", render: (r) => <span className="font-mono text-caption">{r.expression}</span> },
          { header: "Source", render: (r) => <span className="font-mono text-caption">{r.source_ref ?? "—"}</span> },
        ]}
        rows={formulas}
        keyOf={(r) => r.formula_id}
      />
      <p className="max-w-prose text-caption text-text-3">
        Appendix rule: a printed reviewer holding only this payload can recompute every traced
        value from its expression and operands. Procedural roots (cohort statistics, fitted
        shape, calibration quantile) are pipeline-deterministic and reported separately.
      </p>
    </div>
  );
}

