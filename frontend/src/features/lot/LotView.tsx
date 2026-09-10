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
import { InvestigationSection } from "../../design/InvestigationSection";
import { Metric } from "../../design/Metric";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { SeverityChip } from "../../design/SeverityChip";
import { StateBlock } from "../../design/StateBlock";
import { severityOf } from "../../design/severityMap";
import { Badge, StatTile } from "../../design/ui/Badge";
import { Button } from "../../design/ui/Button";
import { EmptyState, Notice } from "../../design/ui/Feedback";
import { MetaList, PageHeader } from "../../design/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "../../design/ui/Panel";

interface DistributionPayload {
  lot_id: string;
  parameters: Array<{
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
  }>;
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

/** S2 Lot Explorer: distribution with DPAT limits, chamber map, signal members. */
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
    setRunState({ kind: "running", label: kind === "anomaly" ? "Module A" : "Module B" });
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
          label: kind === "anomaly" ? "Module A worklist" : "Module B worklist",
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
          message: err instanceof ApiError ? `${err.code}: ${err.message}` : "Run failed.",
        });
      });
  };

  const runDisposition = (): void => {
    setRunState({ kind: "running", label: "Lot disposition (PDA)" });
    apiGet<unknown>(`/lots/${encodeURIComponent(lotId)}/disposition`, 240000)
      .then((res) => {
        setDisposition(res.data);
        setDispMeta(res.meta);
        setRunState({ kind: "idle" });
      })
      .catch((err: unknown) => {
        setRunState({
          kind: "failed",
          message: err instanceof ApiError ? `${err.code}: ${err.message}` : "Run failed.",
        });
      });
  };

  return (
    <>
      <PageHeader
        eyebrow={`S2 · #/lots/${lotId}`}
        title={lotId}
        monoTitle
        description="Lot distribution with DPAT limits drawn on it; the parts that sit outside them."
        badges={
          dist.data !== null ? (
            <Badge tone="neutral">{dist.data.parameters.length} parameters</Badge>
          ) : undefined
        }
      />

      <StateBlock
        status={dist.status}
        error={dist.error}
        onRetry={dist.retry}
        testId="s2-dist"
        skeletonRows={6}
        empty={
          <EmptyState
            title="Unknown lot or no dataset ingested"
            description="This lot id is not present in the active dataset. Ingest a screening corpus, or pick a lot from Mission Control."
            action={
              <Button variant="primary" onClick={() => navigate({ surface: "S1" })}>
                Back to Mission Control
              </Button>
            }
          />
        }
      >
        {dist.meta !== null && <ProvenanceHeader meta={dist.meta} testId="s2-provenance" />}
        {dist.data !== null && (
          <LotDistributions
            dist={dist.data}
            stats={stats.data}
            identities={identities}
            lotId={lotId}
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

function LotDistributions({
  dist,
  stats,
  identities,
  lotId,
  runState,
  onRunModule,
  onRunDisposition,
  disposition,
  dispMeta,
}: {
  dist: DistributionPayload;
  stats: StatisticsPayload | null;
  identities: ComponentIdentity[] | null;
  lotId: string;
  runState: RunState;
  onRunModule: (kind: "anomaly" | "drift") => void;
  onRunDisposition: () => void;
  disposition: unknown | null;
  dispMeta: Meta | null;
}): React.JSX.Element {
  const flaggedByParam = useMemo(
    () =>
      dist.parameters.map((p) => ({
        parameter: p.parameter,
        flagged: p.members.filter((m) => m.flagged),
      })),
    [dist.parameters],
  );
  const totalFlagged = useMemo(
    () => new Set(flaggedByParam.flatMap((f) => f.flagged.map((m) => m.component_id))),
    [flaggedByParam],
  );

  const cells: ChamberCell[] = useMemo(
    () =>
      (identities ?? []).map((c) => {
        const flagged = flaggedByParam.some((f) =>
          f.flagged.some((m) => m.component_id === c.component_id),
        );
        return {
          component_id: c.component_id,
          socket_id: c.socket_id ?? null,
          thermal_zone: c.thermal_zone ?? null,
          severity: severityOf(flagged ? "FAIL" : "PASS"),
          flagged,
          label: flagged ? "DPAT signal in this lot" : "no DPAT signal",
        };
      }),
    [identities, flaggedByParam],
  );

  const running = runState.kind === "running";
  const nParts = identities?.length ?? null;

  return (
    <>
      <section
        aria-label="Lot summary"
        className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
      >
        <StatTile label="Parts in lot" value={nParts ?? "…"} hint="from the component directory" />
        <StatTile
          label="Parts with signals"
          value={totalFlagged.size}
          tone={totalFlagged.size > 0 ? "severe" : "nominal"}
          hint="outside DPAT limits at 24 h"
        />
        <StatTile label="Parameters" value={dist.parameters.length} hint="screening-visible" />
        <StatTile
          label="Cohort mode"
          value={<span className="text-num">{dist.parameters[0]?.cohort_mode ?? "—"}</span>}
          hint="basis for the lot statistics"
        />
      </section>

      {/* Batch runs are the only expensive actions on this surface, so they
          are grouped and labelled with their cost rather than sitting inline
          with navigation. */}
      <Panel>
        <PanelHeader
          title="Lot-wide analysis"
          hint="Batch runs assemble every part server-side and can take a minute on large lots."
        />
        <PanelBody>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => onRunModule("anomaly")}
              busy={running && runState.label === "Module A"}
              disabled={running}
              data-testid="s2-run-anomaly"
            >
              Run Module A over lot
            </Button>
            <Button
              variant="secondary"
              onClick={() => onRunModule("drift")}
              busy={running && runState.label === "Module B"}
              disabled={running}
              data-testid="s2-run-drift"
            >
              Run Module B over lot
            </Button>
            <Button
              variant="secondary"
              onClick={onRunDisposition}
              busy={running && runState.label === "Lot disposition (PDA)"}
              disabled={running}
              data-testid="s2-run-disposition"
            >
              Compute lot disposition (PDA)
            </Button>
          </div>

          {running && (
            <Notice tone="info" testId="s2-run-loading" glyph="↻">
              <p className="text-body text-text-1">
                Running <span className="font-mono text-text-num">{runState.label}</span>…
              </p>
              <p className="mt-1 text-caption text-text-3">
                The backend is assembling every part; nothing is computed in this browser.
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
        <InvestigationSection
          index="R"
          title={runState.label}
          testId="s2-run-queue"
          actions={<Badge tone="neutral">{runState.rows.length} parts</Badge>}
        >
          <DataTable
            testId="s2-run-queue-table"
            caption="Server-side worklist, worst severity first"
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
                    className="rounded-sm font-mono text-text-num underline decoration-border-2 decoration-dotted underline-offset-4 transition-colors duration-fast hover:decoration-text-num"
                  >
                    {r["component_id"]}
                  </button>
                ),
              },
              { header: "Severity", render: (r) => <SeverityChip value={r["severity"]} /> },
              { header: "Band", render: (r) => <SeverityChip value={r["band"]} /> },
              {
                header: "Recommendation",
                render: (r) => <SeverityChip value={r["recommendation"]} />,
              },
              {
                header: "Worst param",
                render: (r) => (
                  <span className="font-mono text-text-2">{r["worst_parameter"]}</span>
                ),
              },
            ]}
            rows={runState.rows}
            keyOf={(r) => r["component_id"] ?? "unknown"}
          />
        </InvestigationSection>
      )}

      {disposition !== null && (
        <InvestigationSection index="PDA" title="Lot disposition" testId="s2-disposition">
          {dispMeta !== null && <ProvenanceHeader meta={dispMeta} />}
          <DispositionSummary data={disposition} />
        </InvestigationSection>
      )}

      <InvestigationSection
        index="01"
        title="Signal members"
        hint={`${totalFlagged.size} parts sit outside their lot's DPAT limits`}
        testId="s2-signals"
        actions={
          <Badge tone={totalFlagged.size > 0 ? "accent" : "outline"}>
            {totalFlagged.size} / {dist.parameters[0]?.n ?? "—"}
          </Badge>
        }
      >
        {totalFlagged.size === 0 ? (
          <Notice tone="success">
            No DPAT signals in this lot at 24 h. Absolute screening and lot-relative screening
            agree everywhere here.
          </Notice>
        ) : (
          <DataTable
            testId="s2-signal-table"
            caption="Members with DPAT signals, component order (backend flags; browser only partitions)"
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
                    className="rounded-sm font-mono text-text-num underline decoration-border-2 decoration-dotted underline-offset-4 transition-colors duration-fast hover:decoration-text-num"
                  >
                    {r.id}
                  </button>
                ),
              },
              {
                header: "Parameters",
                sortValue: (r) => r.params,
                render: (r) => <span className="font-mono text-text-2">{r.params}</span>,
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
            rows={[...totalFlagged].sort().map((id) => ({
              id,
              params: flaggedByParam
                .filter((f) => f.flagged.some((m) => m.component_id === id))
                .map((f) => f.parameter)
                .join(", "),
            }))}
            keyOf={(r) => r.id}
          />
        )}
      </InvestigationSection>

      {identities !== null && identities.length > 0 && (
        <InvestigationSection
          index="02"
          title="Chamber map"
          hint="Physical position of every part. Select a cell to open its investigation."
          testId="s2-chamber"
        >
          <ChamberMap
            cells={cells}
            selectedId={null}
            onSelect={(id) => navigate({ surface: "S3", componentId: id })}
            testId="s2-chamber-map"
          />
        </InvestigationSection>
      )}

      {dist.parameters.map((p, i) => (
        <InvestigationSection
          index={`0${i + 3}`}
          title={`${p.parameter} · ${p.unit}`}
          hint={p.fully_traced ? undefined : "adapter parameter — plain values, marked ≈"}
          key={p.parameter}
          testId={`s2-param-${p.parameter}`}
          actions={
            <>
              {p.reduced_power && <SeverityChip value="DEGRADED" />}
              <Badge tone="outline">n {p.n}</Badge>
            </>
          }
        >
          <MetaList
            items={[
              { label: "estimator", value: p.estimator },
              { label: "cohort", value: p.cohort_mode },
              { label: "native unit", value: p.native_unit },
            ]}
          />

          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            {isTraced(p.median) && (
              <LabelledMetric label="median">
                <Metric
                  traced={p.median}
                  label={`${p.parameter} median`}
                  testId={`s2-${p.parameter}-median`}
                />
              </LabelledMetric>
            )}
            {isTraced(p.robust_sigma) && (
              <LabelledMetric label="robust σ">
                <Metric
                  traced={p.robust_sigma}
                  label={`${p.parameter} robust sigma`}
                  testId={`s2-${p.parameter}-sigma`}
                />
              </LabelledMetric>
            )}
            {isTraced(p.limit_high) && (
              <LabelledMetric label="DPAT upper limit">
                <Metric
                  traced={p.limit_high}
                  label={`${p.parameter} DPAT upper limit`}
                  testId={`s2-${p.parameter}-limhi`}
                />
              </LabelledMetric>
            )}
          </div>

          {stats !== null && <LotStatsRow stats={stats} parameter={p.parameter} />}

          <CohortStrip
            members={p.members}
            focusId=""
            limitLow={isTraced(p.limit_low) ? p.limit_low.value : null}
            limitHigh={isTraced(p.limit_high) ? p.limit_high.value : null}
            median={isTraced(p.median) ? p.median.value : null}
            absHigh={p.absolute_limit_high}
            unit={p.unit}
            testId={`s2-strip-${p.parameter}`}
          />
          <GuardBanner
            guards={null}
            notices={
              p.reduced_power
                ? ["REDUCED POWER — small cohort; MAD path with finite-sample correction."]
                : []
            }
          />
        </InvestigationSection>
      ))}

      <p className="max-w-prose text-caption text-text-3">
        Viewing lot <span className="font-mono text-text-2">{lotId}</span>. Leave-one-out
        statistics for a specific part are available on the investigation screen.
      </p>
    </>
  );
}

/** Label above a traced value, so a metric strip reads as key/value pairs. */
function LabelledMetric({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <div className="min-w-0">
      <div className="eyebrow">{label}</div>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function LotStatsRow({
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
    <div className="rounded-sm border border-border-1 bg-surface-2 p-3">
      <div className="eyebrow">Quartile basis · leave-one-out available per part</div>
      <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-2">
        {isTraced(entry.q1) && (
          <LabelledMetric label="Q1">
            <Metric traced={entry.q1} label={`${parameter} Q1`} />
          </LabelledMetric>
        )}
        {isTraced(entry.q3) && (
          <LabelledMetric label="Q3">
            <Metric traced={entry.q3} label={`${parameter} Q3`} />
          </LabelledMetric>
        )}
        {isTraced(entry.iqr) && (
          <LabelledMetric label="IQR">
            <Metric traced={entry.iqr} label={`${parameter} IQR`} />
          </LabelledMetric>
        )}
      </div>
    </div>
  );
}

/**
 * Lot disposition payload. The verdict leads; the remaining scalar fields
 * are rendered as a definition list, and nested provenance objects are
 * named rather than stringified.
 */
function DispositionSummary({ data }: { data: unknown }): React.JSX.Element {
  const d = data as Record<string, unknown>;
  const scalar = (v: unknown): string => {
    if (v !== null && typeof v === "object" && "value" in (v as Record<string, unknown>))
      return String((v as Record<string, number>)["value"]);
    if (typeof v === "string" || typeof v === "number") return String(v);
    if (v === null || v === undefined) return "—";
    return "[provenance appendix]";
  };
  const entries = Object.entries(d).filter(([k]) => !["provenance", "lot_verdict"].includes(k));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="eyebrow">Lot verdict</span>
        <SeverityChip
          value={typeof d["lot_verdict"] === "string" ? (d["lot_verdict"] as string) : null}
        />
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-4">
        {entries.map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="eyebrow truncate">{k}</dt>
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
