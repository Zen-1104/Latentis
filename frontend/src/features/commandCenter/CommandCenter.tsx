import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../../api/client";
import type { LotSummary } from "../../api/generated/client";
import { useApi } from "../../hooks/useApi";
import { navigate } from "../../router";
import { formatPlain } from "../../format";
import { DataTable } from "../../design/DataTable";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { StateBlock } from "../../design/StateBlock";
import { SURFACE_COPY, parameterLabel } from "../../design/vocabulary";
import { Badge } from "../../design/ui/Badge";
import { Button } from "../../design/ui/Button";
import { InsightCard, StatStrip, TermHelp } from "../../design/ui/Cards";
import { KeyTakeaway, SectionHeader, TechnicalDetails } from "../../design/ui/Disclosure";
import { EmptyState, Skeleton } from "../../design/ui/Feedback";
import { PageHeader } from "../../design/ui/PageHeader";
import { StatusBadge, VerdictContrast } from "../../design/ui/StatusBadge";
import { Panel, PanelBody, PanelHeader } from "../../design/ui/Panel";
import { cn } from "../../design/ui/cn";
import { resolveEscapeSpotlight, type EscapeHit } from "./escape";

interface LotSignals {
  count: number;
}

/** Count distinct flagged parts across parameters (display aggregation, labelled as such). */
async function fetchLotSignals(lotId: string): Promise<{ count: number }> {
  try {
    const res = await apiGet<{
      parameters: Array<{ members: Array<{ component_id: string; flagged: boolean }> }>;
    }>(`/lots/${encodeURIComponent(lotId)}/distribution`);
    const flagged = new Set<string>();
    for (const p of res.data.parameters) {
      for (const m of p.members) {
        if (m.flagged) flagged.add(m.component_id);
      }
    }
    return { count: flagged.size };
  } catch {
    return { count: 0 };
  }
}

async function mapWithLimit<T, R>(
  items: T[],
  limit: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const out: R[] = [];
  for (let i = 0; i < items.length; i += limit) {
    const chunk = items.slice(i, i + limit);
    const results = await Promise.all(chunk.map(fn));
    out.push(...results);
  }
  return out;
}

interface PosturePayload {
  mission_risk_posture: {
    alpha: number;
    k: number;
    margin_fraction: number;
    pda_limit_pct: number;
    horizon_hours: number;
  };
  risk_weights: Record<string, number | string>;
}

interface DatasetSummary {
  dataset_hash: string;
  file_name: string;
  row_count: number;
  rows_accepted: number;
  rows_rejected: number;
  data_provenance?: string;
}

/**
 * S1 Mission Control — "What needs attention?"
 *
 * The screen leads with the answer: programme scale, then the one finding
 * that needs a human, stated in prose with the two disagreeing verdicts side
 * by side. Provenance hashes and policy constants moved into a disclosure at
 * the foot — they are audit metadata, not an introduction.
 *
 * No lot-wide analysis POSTs fire here; only reads.
 */
export function CommandCenter(): React.JSX.Element {
  const lots = useApi<LotSummary[]>("/lots", { isEmpty: (d) => d.length === 0 });
  const posture = useApi<PosturePayload>("/posture");
  const datasets = useApi<DatasetSummary[]>("/datasets");
  const [signals, setSignals] = useState<Map<string, LotSignals> | null>(null);
  const [escape, setEscape] = useState<EscapeHit | "none" | null>(null);

  useEffect(() => {
    if (lots.status !== "ready" || lots.data === null) return;
    let cancelled = false;
    const lotList = lots.data;
    mapWithLimit(lotList, 8, async (lot) => {
      const sig = await fetchLotSignals(lot.lot_id);
      return [lot.lot_id, { count: sig.count }] as const;
    })
      .then((entries) => {
        if (!cancelled) setSignals(new Map(entries));
      })
      .catch(() => {
        if (!cancelled) setSignals(new Map());
      });
    resolveEscapeSpotlight(lotList.map((l) => l.lot_id))
      .then((hit) => {
        if (!cancelled) setEscape(hit ?? "none");
      })
      .catch(() => {
        if (!cancelled) setEscape("none");
      });
    return () => {
      cancelled = true;
    };
  }, [lots.status, lots.data]);

  // Programme totals are display aggregations over values the backend
  // returned — never a computed metric of our own (INV-1).
  const totals = useMemo(() => {
    const lotList = lots.data ?? [];
    const ds = (datasets.data ?? [])[0] ?? null;
    const flagged =
      signals === null ? null : [...signals.values()].reduce((s, v) => s + v.count, 0);
    const lotsAffected =
      signals === null ? null : [...signals.values()].filter((v) => v.count > 0).length;
    return {
      lots: lotList.length,
      components: lotList.reduce((s, l) => s + l.n_parts, 0),
      measurements: ds?.row_count ?? null,
      accepted: ds?.rows_accepted ?? null,
      rejected: ds?.rows_rejected ?? null,
      flagged,
      lotsAffected,
    };
  }, [lots.data, datasets.data, signals]);

  const quality =
    totals.measurements !== null && totals.accepted !== null && totals.measurements > 0
      ? (totals.accepted / totals.measurements) * 100
      : null;

  return (
    <>
      <PageHeader
        question={SURFACE_COPY.S1?.question ?? ""}
        title="Mission Control"
        description={SURFACE_COPY.S1?.summary ?? ""}
        eyebrow="S1 · #/"
        actions={
          <Button variant="ghost" size="sm" onClick={() => navigate({ surface: "S7" })}>
            Data &amp; Quality →
          </Button>
        }
      />

      <StateBlock
        status={lots.status}
        error={lots.error}
        onRetry={lots.retry}
        testId="s1-lots"
        skeletonRows={5}
        empty={
          <EmptyState
            title="No screening dataset has been loaded yet"
            glyph="↻"
            description="Choose a dataset in Data & Quality to begin. Nothing on this screen is computed until a dataset is in place."
            action={
              <Button variant="primary" onClick={() => navigate({ surface: "S7" })}>
                Go to Data &amp; Quality
              </Button>
            }
          />
        }
      >
        {/* ---------- Programme scale, in plain numbers ---------- */}
        <section aria-label="Programme overview" className="space-y-4">
          <SectionHeader
            title="Programme overview"
            hint="What is currently loaded and being screened."
            size="sm"
          />
          <StatStrip
            testId="s1-totals"
            items={[
              {
                label: "Lots",
                value: totals.lots,
                hint: "manufacturing batches loaded",
              },
              {
                label: "Components",
                value: totals.components.toLocaleString(),
                hint: "parts under screening",
              },
              {
                label: "Measurements",
                value: totals.measurements === null ? "—" : totals.measurements.toLocaleString(),
                hint:
                  totals.measurements === null
                    ? "no dataset summary"
                    : "readings in the dataset",
              },
              {
                label: "Readings accepted",
                value: quality === null ? "—" : formatPlain(quality, 2),
                unit: quality === null ? undefined : "%",
                tone: quality !== null && quality >= 99 ? "nominal" : "elevated",
                hint:
                  totals.rejected === null
                    ? "no dataset summary"
                    : `${totals.rejected.toLocaleString()} readings rejected`,
              },
            ]}
          />
        </section>

        {/* ---------- The one thing that needs a human ---------- */}
        <section aria-label="Attention required" className="space-y-4">
          <SectionHeader
            title="Attention required"
            hint="Components that conventional screening would release, but LATENTIS would not."
            size="sm"
            actions={
              totals.flagged !== null ? (
                <Badge tone={totals.flagged > 0 ? "accent" : "outline"}>
                  {totals.flagged} flagged across {totals.lotsAffected} lots
                </Badge>
              ) : undefined
            }
          />
          <EscapeSpotlight escape={escape} />
        </section>

        {/* ---------- Where the problems are concentrated ---------- */}
        <LotHealth lots={lots.data ?? []} signals={signals} />

        {/* ---------- The full list ---------- */}
        <Panel>
          <PanelHeader
            title="All lots"
            hint="Select a lot to see how it is behaving."
            actions={
              <span className="flex items-center gap-2 font-mono text-caption text-text-3">
                {signals === null ? (
                  <>
                    <Skeleton className="h-3 w-3" rounded="full" />
                    checking each lot…
                  </>
                ) : (
                  `${totals.lots} lots`
                )}
              </span>
            }
          />
          <PanelBody>
            <DataTable
              bare
              testId="s1-lot-table"
              caption="One row per manufacturing lot. Flagged counts are a display total over the flags the backend reported."
              maxBodyHeight
              columns={[
                {
                  header: "Lot",
                  rowHeader: true,
                  sortValue: (r) => r.lot_id,
                  render: (r) => (
                    <button
                      type="button"
                      onClick={() => navigate({ surface: "S2", lotId: r.lot_id })}
                      className="rounded-sm font-mono text-accent-hi underline decoration-accent-line decoration-dotted underline-offset-4 transition-colors duration-fast hover:text-text-num hover:decoration-accent-hi"
                      data-testid={`s1-lot-${r.lot_id}`}
                    >
                      {r.lot_id}
                    </button>
                  ),
                },
                {
                  header: "Part type",
                  sortValue: (r) => r.component_type,
                  render: (r) => (
                    <span className="text-text-2">{r.component_type.replace(/_/g, " ")}</span>
                  ),
                },
                {
                  header: "Components",
                  numeric: true,
                  sortValue: (r) => r.n_parts,
                  render: (r) => String(r.n_parts),
                },
                {
                  header: "Need attention",
                  numeric: true,
                  sortValue: (r) => signals?.get(r.lot_id)?.count ?? -1,
                  render: (r) => {
                    const sig = signals?.get(r.lot_id);
                    if (sig === undefined) return <Skeleton className="ml-auto h-3 w-4" />;
                    return sig.count > 0 ? (
                      <span className="font-semibold text-sev-severe">
                        <span aria-hidden="true">✗</span> {sig.count}
                      </span>
                    ) : (
                      <span className="text-sev-nominal">
                        <span aria-hidden="true">✓</span> none
                      </span>
                    );
                  },
                },
                {
                  header: "Data source",
                  secondary: true,
                  render: (r) => <Badge tone="outline">{r.data_provenance}</Badge>,
                },
                {
                  header: "",
                  render: (r) => (
                    <Button
                      variant="quiet"
                      size="sm"
                      onClick={() => navigate({ surface: "S2", lotId: r.lot_id })}
                      aria-label={`Open lot ${r.lot_id}`}
                    >
                      Open →
                    </Button>
                  ),
                },
              ]}
              rows={lots.data ?? []}
              keyOf={(r) => r.lot_id}
            />
          </PanelBody>
        </Panel>

        {/* ---------- Audit metadata, out of the way ---------- */}
        <TechnicalDetails
          label="Technical details"
          hint="dataset identity, screening settings and model versions"
          testId="s1-technical"
        >
          {lots.meta !== null && <ProvenanceHeader meta={lots.meta} testId="s1-provenance" />}
          <PostureGrid posture={posture.status === "ready" ? posture.data : null} />
        </TechnicalDetails>
      </StateBlock>
    </>
  );
}

/**
 * "Which lots need attention?" — a ranked horizontal bar, limited to lots
 * that actually have flagged parts. A chart of forty mostly-empty bars would
 * answer nothing, so the empty case says so in words instead.
 */
/**
 * How many ranked lots the panel shows before deferring to the full table.
 * Six fits without scrolling and keeps the ranking readable; the complete
 * list already lives in "All lots" directly below.
 */
const VISIBLE_LOTS = 6;

function LotHealth({
  lots,
  signals,
}: {
  lots: LotSummary[];
  signals: Map<string, LotSignals> | null;
}): React.JSX.Element | null {
  if (signals === null) {
    return (
      <Panel>
        <PanelHeader title="Which lots need attention?" />
        <PanelBody>
          <div className="space-y-2" role="status" aria-label="Checking each lot">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </PanelBody>
      </Panel>
    );
  }

  const ranked = lots
    .map((l) => ({
      lot: l,
      count: signals.get(l.lot_id)?.count ?? 0,
    }))
    .filter((r) => r.count > 0)
    .sort((a, b) => b.count - a.count || a.lot.lot_id.localeCompare(b.lot.lot_id));

  const worst = ranked[0];
  const clean = lots.length - ranked.length;

  return (
    <Panel>
      <PanelHeader
        title="Which lots need attention?"
        hint="Components flagged by peer comparison, highest first. Lots with none are omitted."
      />
      <PanelBody>
        {ranked.length === 0 ? (
          <KeyTakeaway tone="nominal">
            No component in any of the {lots.length} loaded lots was flagged by peer
            comparison. Absolute screening and lot-relative screening agree everywhere.
          </KeyTakeaway>
        ) : (
          <>
            <ul className="-mx-2 space-y-1">
              {ranked.slice(0, VISIBLE_LOTS).map((r) => {
                const share = worst !== undefined && worst.count > 0 ? r.count / worst.count : 0;
                const pct = r.lot.n_parts > 0 ? (r.count / r.lot.n_parts) * 100 : 0;
                return (
                  <li key={r.lot.lot_id}>
                    <button
                      type="button"
                      onClick={() => navigate({ surface: "S2", lotId: r.lot.lot_id })}
                      className={cn(
                        "grid w-full items-center gap-3 text-left",
                        "grid-cols-[minmax(0,7rem)_minmax(0,1fr)_auto]",
                        "sm:grid-cols-[minmax(0,8rem)_minmax(0,18rem)_1fr]",
                        "rounded-sm px-2 py-2 transition-colors duration-fast hover:bg-hover",
                      )}
                      aria-label={`Lot ${r.lot.lot_id}: ${r.count} of ${r.lot.n_parts} components flagged`}
                    >
                      <span className="truncate font-mono text-caption text-text-num">
                        {r.lot.lot_id}
                      </span>
                      <span
                        aria-hidden="true"
                        className="h-bar-thin overflow-hidden rounded-full bg-surface-0"
                      >
                        <span
                          className="block h-full rounded-full bg-sev-severe"
                          style={{ width: `${Math.max(4, share * 100)}%` }}
                        />
                      </span>
                      <span
                        className="whitespace-nowrap font-mono text-caption text-text-2 tnum"
                        data-tabular-nums="true"
                      >
                        {r.count} / {r.lot.n_parts} ({formatPlain(pct, 1)}%)
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {ranked.length > VISIBLE_LOTS && (
              <p className="font-mono text-caption text-text-3">
                {ranked.length - VISIBLE_LOTS} further lots also have flagged components —
                the full list is below.
              </p>
            )}
            {worst !== undefined && (
              <KeyTakeaway tone="severe">
                {ranked.length} of {lots.length} lots contain components that stand out from
                their peers. {worst.lot.lot_id} has the most — {worst.count} of{" "}
                {worst.lot.n_parts} components. The remaining {clean} lots are clean.
              </KeyTakeaway>
            )}
          </>
        )}
      </PanelBody>
    </Panel>
  );
}

/** Screening settings, shown as labelled values rather than a constant strip. */
function PostureGrid({ posture }: { posture: PosturePayload | null }): React.JSX.Element | null {
  if (posture === null) return null;
  const p = posture.mission_risk_posture;
  const rows: Array<{ key: string; label: string; value: string }> = [
    { key: "k", label: "Peer-comparison threshold", value: `${formatPlain(p.k, 1)} σ` },
    { key: "alpha", label: "Uncertainty level", value: `${formatPlain(p.alpha * 100, 0)}%` },
    {
      key: "margin_fraction",
      label: "Safety reserve",
      value: `${formatPlain(p.margin_fraction * 100, 0)}%`,
    },
    {
      key: "pda_limit_pct",
      label: "Lot reject ceiling",
      value: `${formatPlain(p.pda_limit_pct, 1)}%`,
    },
    {
      key: "horizon_hours",
      label: "Forecast horizon",
      value: `${formatPlain(p.horizon_hours, 0)} h`,
    },
  ];

  return (
    <section aria-label="Screening settings" data-testid="s1-posture" className="space-y-3">
      <p className="eyebrow">Screening settings in force</p>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((r) => (
          <div key={r.key} className="min-w-0">
            <dt className="flex items-center gap-2 text-caption text-text-3">
              <span className="truncate">{r.label}</span>
              <TermHelp setting={r.key} label={r.label} />
            </dt>
            <dd
              className="mt-1 font-mono text-num text-text-num tnum"
              data-tabular-nums="true"
            >
              {r.value}
            </dd>
          </div>
        ))}
      </dl>
      <p className="max-w-prose text-caption text-text-3">
        These are policy inputs read from the active screening profile. They are not chosen
        here, and they cannot move a component across a verdict boundary.
      </p>
    </section>
  );
}

/**
 * The product's central moment: a component conventional screening would
 * ship, that its own lot rejects. Stated as a sentence, with the two
 * disagreeing verdicts placed side by side and the supporting numbers below.
 */
function EscapeSpotlight({ escape }: { escape: EscapeHit | "none" | null }): React.JSX.Element {
  if (escape === null) {
    return (
      <Panel testId="s1-spotlight-loading">
        <div className="space-y-3 p-5" role="status" aria-label="Scanning lots for latent escapes">
          <Skeleton className="h-3 w-1/4" />
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </Panel>
    );
  }

  if (escape === "none") {
    return (
      <Panel testId="s1-spotlight-empty">
        <PanelHeader title="No latent escapes found" actions={<StatusBadge value="PASS" withHelp />} />
        <PanelBody>
          <p className="max-w-prose text-body text-text-2">
            In the lots scanned, no component passed its absolute limit while being rejected by
            its own lot. The two screening methods agree everywhere scanned.
          </p>
        </PanelBody>
      </Panel>
    );
  }

  const paramName = parameterLabel(escape.parameter);

  return (
    <InsightCard
      testId="s1-spotlight"
      tone="severe"
      eyebrow="Latent escape"
      title={
        <button
          type="button"
          onClick={() => navigate({ surface: "S3", componentId: escape.componentId })}
          data-testid="s1-spotlight-open"
          className={cn(
            "break-all rounded-sm text-left font-mono",
            "underline decoration-border-2 decoration-dotted underline-offset-4",
            "transition-colors duration-fast hover:decoration-text-num",
          )}
        >
          {escape.componentId}
        </button>
      }
      body={
        <>
          <p>
            This component is <strong className="font-semibold text-text-1">within</strong> the
            fixed limit for {paramName.toLowerCase()}, so conventional screening would release
            it. Compared with the other components in its own lot, it is a strong outlier —
            which is what LATENTIS exists to catch.
          </p>
          <div className="mt-4">
            <VerdictContrast
              testId="s1-spotlight-contrast"
              leftLabel="Conventional screening"
              leftValue="PASS"
              leftHint="Measured against the fixed limit that applies to every part."
              rightLabel="LATENTIS peer comparison"
              rightValue="FAIL"
              rightHint="Measured against the other components in this same lot."
            />
          </div>
        </>
      }
      facts={[
        { label: "Lot", value: escape.lotId },
        { label: "Measurement", value: paramName },
        {
          label: "Observed",
          value: `${formatPlain(escape.observed, 2)} ${escape.unit}`,
        },
        {
          label: "Distance from peers",
          value: `${formatPlain(escape.z)} σ`,
          tone: "severe",
        },
        ...(escape.dpatLimitHigh !== null
          ? [
              {
                label: "Peer limit",
                value: `${formatPlain(escape.dpatLimitHigh)} ${escape.dpatLimitUnit ?? escape.unit}`,
              },
            ]
          : []),
        ...(escape.absoluteLimitHigh !== null
          ? [
              {
                label: "Fixed limit",
                value: `${formatPlain(escape.absoluteLimitHigh)} ${escape.absoluteLimitUnit ?? ""}`.trim(),
              },
            ]
          : []),
        ...(escape.absoluteMarginPct !== null
          ? [
              {
                label: "Headroom to fixed limit",
                value: `${formatPlain(escape.absoluteMarginPct * 100, 0)}%`,
              },
            ]
          : []),
      ]}
      action={
        <>
          <Button
            variant="primary"
            onClick={() => navigate({ surface: "S3", componentId: escape.componentId })}
          >
            Investigate this component →
          </Button>
          <Button
            variant="secondary"
            onClick={() => navigate({ surface: "S2", lotId: escape.lotId })}
          >
            See its lot
          </Button>
        </>
      }
    />
  );
}
