import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost, ApiError } from "../../api/client";
import type { ComponentIdentity, LotStatistics, Meta } from "../../api/generated/client";
import { useApi } from "../../hooks/useApi";
import { navigate } from "../../router";
import { isTraced } from "../../format";
import { ChamberMap, type ChamberCell } from "../../design/ChamberMap";
import { CohortStrip, type StripMember } from "../../design/CohortStrip";
import { DataTable } from "../../design/DataTable";
import { GuardBanner } from "../../design/GuardBanner";
import { Metric } from "../../design/Metric";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { StateBlock } from "../../design/StateBlock";
import { severityOf } from "../../design/severityMap";
import {
  SURFACE_COPY,
  methodLabel,
  parameterLabel,
  parameterTerm,
} from "../../design/vocabulary";
import { Badge } from "../../design/ui/Badge";
import { Button } from "../../design/ui/Button";
import { StatStrip, TermHelp } from "../../design/ui/Cards";
import { KeyTakeaway, SectionHeader, TechnicalDetails } from "../../design/ui/Disclosure";
import { EmptyState, Notice } from "../../design/ui/Feedback";
import { PageHeader } from "../../design/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "../../design/ui/Panel";
import { StatusBadge } from "../../design/ui/StatusBadge";
import { Tabs, TabPanel } from "../../design/ui/Tabs";
import { cn } from "../../design/ui/cn";

interface DistParam {
  parameter: string;
  unit: string;
  native_unit: string;
  fully_traced: boolean;
  n: number;
  cohort_mode: string;
  median: unknown;
  robust_sigma: unknown;
  limit_low: unknown;
  limit_high: unknown;
  absolute_limit_high: number | null;
  absolute_limit_low: number | null;
  members: StripMember[];
  estimator: string;
  reduced_power: boolean;
}

interface DistributionPayload {
  lot_id: string;
  parameters: DistParam[];
}

interface StatisticsPayload {
  lot_id: string;
  cohort_mode: string;
  parameters: LotStatistics[];
}

interface ComponentDirectory {
  items: ComponentIdentity[];
  next_cursor: string | null;
}

type RunState =
  | { kind: "idle" }
  | { kind: "running"; label: string }
  | { kind: "queue"; label: string; rows: Array<Record<string, string>> }
  | { kind: "failed"; message: string };

async function fetchAllComponents(lotId: string): Promise<ComponentIdentity[]> {
  const items: ComponentIdentity[] = [];
  let cursor: string | null = "0";
  while (cursor !== null) {
    const page: string = cursor;
    const res: { data: ComponentDirectory; meta: Meta } = await apiGet<ComponentDirectory>(
      `/components?lot_id=${encodeURIComponent(lotId)}&limit=200&cursor=${encodeURIComponent(page)}`,
    );
    items.push(...res.data.items);
    cursor = res.data.next_cursor;
  }
  return items;
}

/**
 * S2 Lot Explorer — "How is this lot behaving?"
 *
 * Leads with the lot's health and which measurement is responsible, then the
 * specific components, then the physical layout. The six per-measurement
 * breakdowns used to render at once — six metric strips, six plots and six
 * tables stacked down the page — so they now sit behind a selector and only
 * the chosen one is drawn.
 */
export function LotView({ lotId }: { lotId: string }): React.JSX.Element {
  const stats = useApi<StatisticsPayload>(`/lots/${encodeURIComponent(lotId)}/statistics`);
  const dist = useApi<DistributionPayload>(`/lots/${encodeURIComponent(lotId)}/distribution`);
  const [identities, setIdentities] = useState<ComponentIdentity[] | null>(null);
  const [runState, setRunState] = useState<RunState>({ kind: "idle" });
  const [disposition, setDisposition] = useState<unknown | null>(null);
  const [dispMeta, setDispMeta] = useState<Meta | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchAllComponents(lotId)
      .then((items) => {
        if (!cancelled) setIdentities(items);
      })
      .catch(() => {
        if (!cancelled) setIdentities([]);
      });
    return () => {
      cancelled = true;
    };
  }, [lotId]);

  const runModule = (kind: "anomaly" | "drift"): void => {
    setRunState({
      kind: "running",
      label: kind === "anomaly" ? "Peer comparison" : "Trend analysis",
    });
    apiPost<{
      run_id: string;
      n_parts: number;
      queue: Array<{
        component_id: string;
        severity: string;
        band: string;
        recommendation: string;
        worst_parameter: string;
      }>;
    }>(`/lots/${encodeURIComponent(lotId)}/${kind}`, undefined, 240000)
      .then((res) => {
        setRunState({
          kind: "queue",
          label: kind === "anomaly" ? "Peer-comparison worklist" : "Trend-analysis worklist",
          rows: res.data.queue.map((q) => ({
            component_id: q.component_id,
            severity: q.severity,
            band: q.band,
            recommendation: q.recommendation,
            worst_parameter: q.worst_parameter,
          })),
        });
      })
      .catch((err: unknown) => {
        setRunState({
          kind: "failed",
          message:
            err instanceof ApiError ? `${err.code}: ${err.message}` : "The run did not finish.",
        });
      });
  };

  const runDisposition = (): void => {
    setRunState({ kind: "running", label: "Lot disposition" });
    apiGet<unknown>(`/lots/${encodeURIComponent(lotId)}/disposition`, 240000)
      .then((res) => {
        setDisposition(res.data);
        setDispMeta(res.meta);
        setRunState({ kind: "idle" });
      })
      .catch((err: unknown) => {
        setRunState({
          kind: "failed",
          message:
            err instanceof ApiError ? `${err.code}: ${err.message}` : "The run did not finish.",
        });
      });
  };

  return (
    <>
      <PageHeader
        question={SURFACE_COPY.S2?.question ?? ""}
        crumbs={[{ label: "Mission Control", to: { surface: "S1" } }, { label: lotId }]}
        title={lotId}
        monoTitle
        description={SURFACE_COPY.S2?.summary ?? ""}
        eyebrow={`S2 · #/lots/${lotId}`}
      />

      <StateBlock
        status={dist.status}
        error={dist.error}
        onRetry={dist.retry}
        testId="s2-dist"
        skeletonRows={6}
        empty={
          <EmptyState
            title="This lot is not in the loaded dataset"
            description="Pick a lot from Mission Control, or load a dataset in Data & Quality."
            action={
              <Button variant="primary" onClick={() => navigate({ surface: "S1" })}>
                Back to Mission Control
              </Button>
            }
          />
        }
      >
        {dist.data !== null && (
          <LotBody
            dist={dist.data}
            stats={stats.data}
            identities={identities}
            meta={dist.meta}
            runState={runState}
            onRunModule={runModule}
            onRunDisposition={runDisposition}
            disposition={disposition}
            dispMeta={dispMeta}
          />
        )}
      </StateBlock>
    </>
  );
}

function LotBody({
  dist,
  stats,
  identities,
  meta,
  runState,
  onRunModule,
  onRunDisposition,
  disposition,
  dispMeta,
}: {
  dist: DistributionPayload;
  stats: StatisticsPayload | null;
  identities: ComponentIdentity[] | null;
  meta: Meta | null;
  runState: RunState;
  onRunModule: (kind: "anomaly" | "drift") => void;
  onRunDisposition: () => void;
  disposition: unknown | null;
  dispMeta: Meta | null;
}): React.JSX.Element {
  const params = dist.parameters;
  const [active, setActive] = useState<string>(params[0]?.parameter ?? "");
  const current = params.find((p) => p.parameter === active) ?? params[0];

  const perParam = useMemo(
    () =>
      params.map((p) => ({
        parameter: p.parameter,
        label: parameterLabel(p.parameter),
        n: p.n,
        flagged: p.members.filter((m) => m.flagged).length,
      })),
    [params],
  );

  const flaggedIds = useMemo(() => {
    const set = new Set<string>();
    for (const p of params) {
      for (const m of p.members) if (m.flagged) set.add(m.component_id);
    }
    return set;
  }, [params]);

  const worstParam = useMemo(
    () => [...perParam].sort((a, b) => b.flagged - a.flagged)[0] ?? null,
    [perParam],
  );

  const cells: ChamberCell[] = useMemo(
    () =>
      (identities ?? []).map((c) => {
        const flagged = flaggedIds.has(c.component_id);
        return {
          component_id: c.component_id,
          socket_id: c.socket_id ?? null,
          thermal_zone: c.thermal_zone ?? null,
          severity: severityOf(flagged ? "FAIL" : "PASS"),
          flagged,
          label: flagged ? "stands out from its peers" : "behaving like its peers",
        };
      }),
    [identities, flaggedIds],
  );

  const running = runState.kind === "running";
  const nParts = identities?.length ?? null;
  const maxFlagged = Math.max(...perParam.map((x) => x.flagged), 1);

  return (
    <>
      {/* ---------- Lot health at a glance ---------- */}
      <section aria-label="Lot health" className="space-y-4">
        <SectionHeader
          title="Lot health"
          hint="How many components in this lot stand out from their peers."
          size="sm"
        />
        <StatStrip
          testId="s2-lot-health"
          items={[
            {
              label: "Components",
              value: nParts ?? "…",
              hint: nParts === null ? "loading directory" : "parts in this lot",
            },
            {
              label: "Need attention",
              value: flaggedIds.size,
              tone: flaggedIds.size > 0 ? "severe" : "nominal",
              hint: "flagged by peer comparison",
              conceptKey: "dpat",
            },
            {
              label: "Measurements taken",
              value: params.length,
              hint: "per component",
            },
            {
              label: "Comparison group",
              // A method name, not a figure — it takes the reading size so it
              // does not sit at 28px next to three counts.
              value: <span className="text-num">{methodLabel(params[0]?.cohort_mode)}</span>,
              hint: "basis for the peer comparison",
            },
          ]}
        />
      </section>

      {/* ---------- Which measurement is responsible ---------- */}
      <Panel>
        <PanelHeader
          title="Which measurement is flagging components?"
          hint="Components flagged by peer comparison, per measurement. Select one to inspect it."
        />
        <PanelBody>
          <ul className="space-y-2">
            {perParam.map((p) => {
              const share = p.flagged / maxFlagged;
              return (
                <li key={p.parameter}>
                  <button
                    type="button"
                    onClick={() => setActive(p.parameter)}
                    className={cn(
                      "grid w-full grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-3",
                      "rounded-sm px-1 py-1 text-left transition-colors duration-fast hover:bg-hover",
                      p.parameter === active && "bg-surface-2",
                    )}
                    aria-label={`${p.label}: ${p.flagged} of ${p.n} components flagged`}
                  >
                    <span className="truncate text-body text-text-1">{p.label}</span>
                    <span
                      aria-hidden="true"
                      className="h-bar overflow-hidden rounded-full bg-surface-2"
                    >
                      <span
                        className={cn(
                          "block h-full rounded-full",
                          p.flagged > 0 ? "bg-sev-severe" : "bg-sev-nominal",
                        )}
                        style={{ width: p.flagged > 0 ? `${Math.max(4, share * 100)}%` : "2%" }}
                      />
                    </span>
                    <span
                      className="whitespace-nowrap font-mono text-caption text-text-2 tnum"
                      data-tabular-nums="true"
                    >
                      {p.flagged} / {p.n}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {worstParam !== null && worstParam.flagged > 0 ? (
            <KeyTakeaway tone="severe">
              {worstParam.label} accounts for most of what stands out in this lot —{" "}
              {worstParam.flagged} of {worstParam.n} components. One measurement dominating like
              this points at a single shared mechanism rather than scattered individual faults.
            </KeyTakeaway>
          ) : (
            <KeyTakeaway tone="nominal">
              No measurement flagged any component in this lot. Absolute screening and peer
              comparison agree throughout.
            </KeyTakeaway>
          )}
        </PanelBody>
      </Panel>

      {/* ---------- The specific components ---------- */}
      <Panel testId="s2-signals">
        <PanelHeader
          title="Components that need attention"
          hint="Select one to see the full evidence behind its flag."
          actions={
            <Badge tone={flaggedIds.size > 0 ? "accent" : "outline"}>
              {flaggedIds.size} of {nParts ?? "…"}
            </Badge>
          }
        />
        <PanelBody>
          {flaggedIds.size === 0 ? (
            <Notice tone="success">
              No component in this lot stands out from its peers at the 24-hour read-point.
            </Notice>
          ) : (
            <DataTable
              bare
              testId="s2-signal-table"
              caption="Flagged components, in component order. Flags come from the backend; the browser only groups them."
              maxBodyHeight
              columns={[
                {
                  header: "Component",
                  rowHeader: true,
                  sortValue: (r) => r.id,
                  render: (r) => (
                    <button
                      type="button"
                      onClick={() => navigate({ surface: "S3", componentId: r.id })}
                      className="rounded-sm font-mono text-accent-hi underline decoration-accent-line decoration-dotted underline-offset-4 transition-colors duration-fast hover:text-text-num hover:decoration-accent-hi"
                    >
                      {r.id}
                    </button>
                  ),
                },
                {
                  header: "Flagged on",
                  sortValue: (r) => r.params,
                  render: (r) => <span className="text-text-2">{r.params}</span>,
                },
                {
                  header: "",
                  render: (r) => (
                    <Button
                      variant="quiet"
                      size="sm"
                      onClick={() => navigate({ surface: "S3", componentId: r.id })}
                      aria-label={`Investigate ${r.id}`}
                    >
                      Investigate →
                    </Button>
                  ),
                },
              ]}
              rows={[...flaggedIds].sort().map((id) => ({
                id,
                params: params
                  .filter((p) => p.members.some((m) => m.component_id === id && m.flagged))
                  .map((p) => parameterLabel(p.parameter))
                  .join(", "),
              }))}
              keyOf={(r) => r.id}
            />
          )}
        </PanelBody>
      </Panel>

      {/* ---------- Physical layout ---------- */}
      {identities !== null && identities.length > 0 && (
        <Panel testId="s2-chamber">
          <PanelHeader
            title="Where these components sit in the oven"
            hint="Each square is one component in its test socket, grouped by oven zone. Flagged components are marked."
          />
          <PanelBody>
            <ChamberMap
              cells={cells}
              selectedId={null}
              onSelect={(id) => navigate({ surface: "S3", componentId: id })}
              testId="s2-chamber-map"
            />
            {flaggedIds.size > 0 && (
              <KeyTakeaway>
                If flagged squares cluster in one zone or one socket column, the cause may be the
                test setup rather than the parts. Scattered flags point at the components
                themselves. Each component&apos;s investigation states which the evidence
                supports.
              </KeyTakeaway>
            )}
          </PanelBody>
        </Panel>
      )}

      {/* ---------- Per-measurement detail, one at a time ---------- */}
      <section aria-label="Measurement detail" className="space-y-4">
        <SectionHeader
          title="Measurement detail"
          hint="How this lot is distributed for one measurement, and where the limits fall."
          size="sm"
          actions={<Badge tone="outline">{params.length} measurements</Badge>}
        />
        <Tabs
          label="Measurements"
          items={params.map((p) => ({
            id: p.parameter,
            label: parameterLabel(p.parameter),
            note:
              p.members.filter((m) => m.flagged).length > 0
                ? String(p.members.filter((m) => m.flagged).length)
                : undefined,
            testId: `s2-tab-${p.parameter}`,
          }))}
          activeId={active}
          onChange={setActive}
          panelId="s2-parameter-panel"
          testIdPrefix="s2-tab-"
        />
        {current !== undefined && (
          <TabPanel
            id="s2-parameter-panel"
            labelledBy={`s2-tab-${current.parameter}-tab`}
            className="space-y-4"
          >
            <ParameterDetail param={current} stats={stats} />
          </TabPanel>
        )}
      </section>

      {/* ---------- Lot-wide analysis ---------- */}
      <Panel>
        <PanelHeader
          title="Run analysis across the whole lot"
          hint="These assemble every component on the server and can take a minute on large lots."
        />
        <PanelBody>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => onRunModule("anomaly")}
              busy={running && runState.label === "Peer comparison"}
              disabled={running}
              data-testid="s2-run-anomaly"
            >
              Rank by peer comparison
            </Button>
            <Button
              variant="secondary"
              onClick={() => onRunModule("drift")}
              busy={running && runState.label === "Trend analysis"}
              disabled={running}
              data-testid="s2-run-drift"
            >
              Rank by trend
            </Button>
            <Button
              variant="secondary"
              onClick={onRunDisposition}
              busy={running && runState.label === "Lot disposition"}
              disabled={running}
              data-testid="s2-run-disposition"
            >
              Assess the lot as a whole
            </Button>
          </div>

          {running && (
            <Notice tone="info" testId="s2-run-loading" glyph="↻">
              <p className="text-body text-text-1">
                Running <span className="font-medium">{runState.label}</span> across every
                component…
              </p>
              <p className="mt-1 text-caption text-text-3">
                The server does this work; nothing is computed in the browser.
              </p>
            </Notice>
          )}
          {runState.kind === "failed" && (
            <Notice tone="error" testId="s2-run-error">
              {runState.message}
            </Notice>
          )}
        </PanelBody>
      </Panel>

      {runState.kind === "queue" && (
        <Panel testId="s2-run-queue">
          <PanelHeader
            title={runState.label}
            hint="Ordered by the server, most concerning first."
            actions={<Badge tone="neutral">{runState.rows.length} components</Badge>}
          />
          <PanelBody>
            <DataTable
              bare
              testId="s2-run-queue-table"
              caption="Server-ordered worklist"
              maxBodyHeight
              columns={[
                {
                  header: "Component",
                  rowHeader: true,
                  render: (r) => (
                    <button
                      type="button"
                      onClick={() =>
                        navigate({ surface: "S3", componentId: r["component_id"] ?? "unknown" })
                      }
                      className="rounded-sm font-mono text-accent-hi underline decoration-accent-line decoration-dotted underline-offset-4 transition-colors duration-fast hover:text-text-num hover:decoration-accent-hi"
                    >
                      {r["component_id"]}
                    </button>
                  ),
                },
                {
                  header: "Peer comparison",
                  render: (r) => <StatusBadge value={r["severity"]} withHelp />,
                },
                { header: "Outlook", render: (r) => <StatusBadge value={r["band"]} withHelp /> },
                {
                  header: "Recommended action",
                  render: (r) => <StatusBadge value={r["recommendation"]} withHelp />,
                },
                {
                  header: "Most affected measurement",
                  render: (r) => (
                    <span className="text-text-2">{parameterLabel(r["worst_parameter"])}</span>
                  ),
                },
              ]}
              rows={runState.rows}
              keyOf={(r) => r["component_id"] ?? "unknown"}
            />
          </PanelBody>
        </Panel>
      )}

      {disposition !== null && (
        <Panel testId="s2-disposition">
          <PanelHeader title="Assessment of the lot as a whole" />
          <PanelBody>
            <LotDisposition data={disposition} />
            {dispMeta !== null && (
              <TechnicalDetails label="Provenance for this assessment">
                <ProvenanceHeader meta={dispMeta} />
              </TechnicalDetails>
            )}
          </PanelBody>
        </Panel>
      )}

      <TechnicalDetails
        label="Technical details"
        hint="dataset identity, model versions and comparison basis"
        testId="s2-technical"
      >
        {meta !== null && <ProvenanceHeader meta={meta} testId="s2-provenance" />}
        <p className="max-w-prose text-caption text-text-3">
          Peer statistics on this screen are lot-wide. A component&apos;s own investigation uses a
          leave-one-out basis, so its numbers are computed without including itself.
        </p>
      </TechnicalDetails>
    </>
  );
}

/** One measurement: what was measured, the peer limits, and the spread. */
function ParameterDetail({
  param,
  stats,
}: {
  param: DistParam;
  stats: StatisticsPayload | null;
}): React.JSX.Element {
  const term = parameterTerm(param.parameter);
  const flagged = param.members.filter((m) => m.flagged).length;

  return (
    <Panel testId={`s2-param-${param.parameter}`}>
      <PanelHeader
        title={parameterLabel(param.parameter)}
        hint={term?.explain}
        actions={
          <>
            {param.reduced_power && <StatusBadge value="DEGRADED" withHelp />}
            {!param.fully_traced && <StatusBadge value="INDETERMINATE" withHelp />}
            <Badge tone="outline">
              {flagged} of {param.n} flagged
            </Badge>
          </>
        }
      />
      <PanelBody>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-3">
          {isTraced(param.median) && (
            <LabelledValue label="Typical for this lot" hint="the middle of the lot">
              <Metric
                traced={param.median}
                label={`${parameterLabel(param.parameter)} lot median`}
                testId={`s2-${param.parameter}-median`}
              />
            </LabelledValue>
          )}
          {isTraced(param.robust_sigma) && (
            <LabelledValue label="Normal spread" hint="how much parts usually differ">
              <Metric
                traced={param.robust_sigma}
                label={`${parameterLabel(param.parameter)} robust spread`}
                testId={`s2-${param.parameter}-sigma`}
              />
            </LabelledValue>
          )}
          {isTraced(param.limit_high) && (
            <LabelledValue label="Peer limit" hint="beyond this a part is flagged" concept="dpat">
              <Metric
                traced={param.limit_high}
                label={`${parameterLabel(param.parameter)} peer upper limit`}
                testId={`s2-${param.parameter}-limhi`}
              />
            </LabelledValue>
          )}
        </dl>

        <figure className="m-0 space-y-3">
          <figcaption className="space-y-1">
            <h3 className="text-h2 font-semibold text-text-1">How is this lot distributed?</h3>
            <p className="max-w-prose text-body text-text-2">
              Every dot is one component. Vertical rules mark the peer limits and the fixed
              limit. Dots outside the peer limits are the flagged components.
            </p>
          </figcaption>
          <CohortStrip
            members={param.members}
            focusId=""
            limitLow={isTraced(param.limit_low) ? param.limit_low.value : null}
            limitHigh={isTraced(param.limit_high) ? param.limit_high.value : null}
            median={isTraced(param.median) ? param.median.value : null}
            absHigh={param.absolute_limit_high}
            unit={param.unit}
            testId={`s2-strip-${param.parameter}`}
          />
        </figure>

        <GuardBanner
          guards={null}
          scope={parameterLabel(param.parameter)}
          notices={
            param.reduced_power
              ? [
                  "SMALL PEER GROUP — this lot has few comparable parts, so the peer comparison is less sensitive than usual.",
                ]
              : []
          }
        />

        <TechnicalDetails label="Statistical detail" hint="estimator, quartiles and units">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            {[
              {
                k: "Spread estimate",
                v: `${methodLabel(param.estimator)} (${param.estimator})`,
              },
              {
                k: "Comparison group",
                v: `${methodLabel(param.cohort_mode)} (${param.cohort_mode})`,
              },
              { k: "Display unit", v: param.unit },
              { k: "Native unit", v: param.native_unit },
              { k: "Peers compared", v: String(param.n) },
              {
                k: "Values carry a calculation trace",
                v: param.fully_traced ? "yes" : "no — plain values, marked ≈",
              },
            ].map((r) => (
              <div key={r.k} className="min-w-0">
                <dt className="eyebrow">{r.k}</dt>
                <dd className="mt-1 break-all font-mono text-caption text-text-num">{r.v}</dd>
              </div>
            ))}
          </dl>
          {stats !== null && <LotQuartiles stats={stats} parameter={param.parameter} />}
        </TechnicalDetails>
      </PanelBody>
    </Panel>
  );
}

function LabelledValue({
  label,
  hint,
  concept,
  children,
}: {
  label: string;
  hint?: string;
  concept?: string;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-2">
        <span className="eyebrow truncate">{label}</span>
        <TermHelp concept={concept} label={label} />
      </dt>
      <dd className="mt-1">{children}</dd>
      {hint !== undefined && <p className="mt-1 text-caption text-text-3">{hint}</p>}
    </div>
  );
}

function LotQuartiles({
  stats,
  parameter,
}: {
  stats: StatisticsPayload;
  parameter: string;
}): React.JSX.Element {
  const entry = stats.parameters.find(
    (s) => (s as unknown as Record<string, unknown>)["parameter"] === parameter,
  ) as (LotStatistics & { parameter?: string }) | undefined;
  if (entry === undefined) return <></>;
  return (
    <div className="space-y-2 border-t border-border-1 pt-3">
      <p className="eyebrow">Quartiles</p>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        {isTraced(entry.q1) && (
          <LabelledValue label="Lower quartile">
            <Metric traced={entry.q1} label={`${parameter} Q1`} />
          </LabelledValue>
        )}
        {isTraced(entry.q3) && (
          <LabelledValue label="Upper quartile">
            <Metric traced={entry.q3} label={`${parameter} Q3`} />
          </LabelledValue>
        )}
        {isTraced(entry.iqr) && (
          <LabelledValue label="Inter-quartile range">
            <Metric traced={entry.iqr} label={`${parameter} IQR`} />
          </LabelledValue>
        )}
      </div>
    </div>
  );
}

/** Lot-level assessment payload, verdict first. */
function LotDisposition({ data }: { data: unknown }): React.JSX.Element {
  const d = data as Record<string, unknown>;
  const scalar = (v: unknown): string => {
    if (v !== null && typeof v === "object" && "value" in (v as Record<string, unknown>))
      return String((v as Record<string, number>)["value"]);
    if (typeof v === "string" || typeof v === "number") return String(v);
    if (v === null || v === undefined) return "—";
    return "see provenance";
  };
  const entries = Object.entries(d).filter(([k]) => !["provenance", "lot_verdict"].includes(k));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="eyebrow">Verdict for the lot</span>
        <StatusBadge
          value={typeof d["lot_verdict"] === "string" ? (d["lot_verdict"] as string) : null}
          size="md"
          withHelp
        />
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-4">
        {entries.map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="eyebrow truncate">{k.replace(/_/g, " ")}</dt>
            <dd
              className="mt-1 break-all font-mono text-num text-text-num tnum"
              data-tabular-nums="true"
            >
              {scalar(v)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
