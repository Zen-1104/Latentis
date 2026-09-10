import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../../api/client";
import type { LotSummary } from "../../api/generated/client";
import { useApi } from "../../hooks/useApi";
import { navigate } from "../../router";
import { formatPlain } from "../../format";
import { DataTable } from "../../design/DataTable";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { SeverityChip } from "../../design/SeverityChip";
import { StateBlock } from "../../design/StateBlock";
import { Badge, StatTile } from "../../design/ui/Badge";
import { Button } from "../../design/ui/Button";
import { EmptyState, Skeleton } from "../../design/ui/Feedback";
import { PageHeader } from "../../design/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "../../design/ui/Panel";
import { InfoHint, Tooltip } from "../../design/ui/Tooltip";
import { resolveEscapeSpotlight, type EscapeHit } from "./escape";

interface LotSignals {
  count: number;
  parts: string[];
}

/** Count distinct flagged parts across parameters (display aggregation, labelled as such). */
async function fetchLotSignals(lotId: string): Promise<{ count: number; parts: string[] }> {
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
    return { count: flagged.size, parts: [...flagged].sort().slice(0, 6) };
  } catch {
    return { count: 0, parts: [] };
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
}

/**
 * S1 Mission Control: provenance first, escape spotlight, lot table.
 * No lot-wide analysis POSTs fire here — only reads.
 */
export function CommandCenter(): React.JSX.Element {
  const lots = useApi<LotSummary[]>("/lots", {
    isEmpty: (d) => d.length === 0,
  });
  const posture = useApi<PosturePayload>("/posture");
  const [signals, setSignals] = useState<Map<string, LotSignals> | null>(null);
  const [escape, setEscape] = useState<EscapeHit | "none" | null>(null);

  useEffect(() => {
    if (lots.status !== "ready" || lots.data === null) return;
    let cancelled = false;
    const lotList = lots.data;
    mapWithLimit(lotList, 8, async (lot) => {
      const sig = await fetchLotSignals(lot.lot_id);
      return [lot.lot_id, { count: sig.count, parts: sig.parts }] as const;
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

  // Fleet totals are display aggregations over backend flags — labelled as
  // such, and never presented as a computed metric (INV-1).
  const totals = useMemo(() => {
    const lotList = lots.data ?? [];
    const parts = lotList.reduce((sum, l) => sum + l.n_parts, 0);
    const flagged =
      signals === null ? null : [...signals.values()].reduce((sum, s) => sum + s.count, 0);
    const lotsWithSignals =
      signals === null ? null : [...signals.values()].filter((s) => s.count > 0).length;
    return { lots: lotList.length, parts, flagged, lotsWithSignals };
  }, [lots.data, signals]);

  return (
    <>
      <PageHeader
        eyebrow="S1 · #/"
        title="Mission Control"
        description="Fleet state, lot summaries, and the escape-risk spotlight. Every number below is computed by the backend from the ingested dataset."
        actions={
          <Button variant="ghost" size="sm" onClick={() => navigate({ surface: "S7" })}>
            Ingest &amp; Quality →
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
            title="No dataset ingested"
            glyph="↻"
            description={
              <>
                Mission Control populates after a screening dataset is ingested. Open Ingest
                &amp; Quality (S7) and upload the screening corpus — or re-ingest it after a
                backend restart, since the active dataset selection is in-memory.
              </>
            }
            action={
              <Button variant="primary" onClick={() => navigate({ surface: "S7" })}>
                Open Ingest &amp; Quality
              </Button>
            }
          />
        }
      >
        {lots.meta !== null && <ProvenanceHeader meta={lots.meta} testId="s1-provenance" />}

        <section
          aria-label="Fleet summary"
          className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
        >
          <StatTile label="Lots" value={totals.lots} hint="in the active dataset" />
          <StatTile label="Parts screened" value={totals.parts} hint="across all lots" />
          <StatTile
            label="Parts with DPAT signals"
            value={totals.flagged ?? "…"}
            tone={totals.flagged !== null && totals.flagged > 0 ? "severe" : "nominal"}
            hint="display aggregation over backend flags"
          />
          <StatTile
            label="Lots with signals"
            value={totals.lotsWithSignals ?? "…"}
            unit={totals.lotsWithSignals !== null ? `/ ${totals.lots}` : undefined}
            hint="at the 24 h read-point"
          />
        </section>

        <PostureStrip posture={posture.status === "ready" ? posture.data : null} />

        <EscapeSpotlight escape={escape} />

        <Panel>
          <PanelHeader
            title="Lots"
            actions={
              <span className="flex items-center gap-2 font-mono text-caption text-text-3">
                {signals === null ? (
                  <>
                    <Skeleton className="h-3 w-3" rounded="full" />
                    counting DPAT signals…
                  </>
                ) : (
                  `${totals.lots} lots`
                )}
              </span>
            }
          />
          <PanelBody flush className="p-4">
            <DataTable
              testId="s1-lot-table"
              caption="Lots with part counts and 24 h DPAT signal counts (display aggregation over backend flags)"
              columns={[
                {
                  header: "Lot",
                  rowHeader: true,
                  sortValue: (r) => r.lot_id,
                  render: (r) => (
                    <button
                      type="button"
                      onClick={() => navigate({ surface: "S2", lotId: r.lot_id })}
                      className="rounded-sm font-mono text-text-num underline decoration-border-2 decoration-dotted underline-offset-4 transition-colors duration-fast hover:decoration-text-num"
                      data-testid={`s1-lot-${r.lot_id}`}
                    >
                      {r.lot_id}
                    </button>
                  ),
                },
                {
                  header: "Type",
                  sortValue: (r) => r.component_type,
                  render: (r) => <span className="font-mono text-text-2">{r.component_type}</span>,
                },
                {
                  header: "n",
                  numeric: true,
                  sortValue: (r) => r.n_parts,
                  render: (r) => String(r.n_parts),
                },
                {
                  header: "DPAT signals",
                  numeric: true,
                  sortValue: (r) => signals?.get(r.lot_id)?.count ?? -1,
                  render: (r) => {
                    const sig = signals?.get(r.lot_id);
                    if (sig === undefined)
                      return <Skeleton className="ml-auto h-3 w-4" />;
                    return sig.count > 0 ? (
                      <span className="font-semibold text-sev-severe">
                        <span aria-hidden="true">✗</span> {sig.count}
                      </span>
                    ) : (
                      <span className="text-sev-nominal">
                        <span aria-hidden="true">✓</span> 0
                      </span>
                    );
                  },
                },
                {
                  header: "Provenance",
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
                      aria-label={`Explore lot ${r.lot_id}`}
                    >
                      Explore →
                    </Button>
                  ),
                },
              ]}
              rows={lots.data ?? []}
              keyOf={(r) => r.lot_id}
            />
          </PanelBody>
        </Panel>
      </StateBlock>
    </>
  );
}

/**
 * The active risk posture. These are the policy inputs every verdict on
 * every other surface is measured against, so they belong on the landing
 * surface rather than buried in the profile screen.
 */
function PostureStrip({ posture }: { posture: PosturePayload | null }): React.JSX.Element | null {
  if (posture === null) return null;
  const p = posture.mission_risk_posture;
  const items: Array<{ label: string; value: string; hint: string }> = [
    { label: "α", value: formatPlain(p.alpha), hint: "Miscoverage rate the conformal bound is calibrated for." },
    { label: "k", value: formatPlain(p.k, 1), hint: "Robust-distance multiplier setting the DPAT limits." },
    {
      label: "margin reserve",
      value: `${formatPlain(p.margin_fraction * 100, 0)}%`,
      hint: "Fraction of the absolute limit held back as usable margin.",
    },
    {
      label: "PDA limit",
      value: `${formatPlain(p.pda_limit_pct, 1)}%`,
      hint: "Percent-defective-allowable ceiling for a lot disposition.",
    },
    {
      label: "horizon",
      value: `${formatPlain(p.horizon_hours, 0)} h`,
      hint: "Forecast horizon every band is evaluated at.",
    },
  ];

  return (
    <Panel testId="s1-posture">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
        <span className="eyebrow flex items-center gap-2">
          Mission risk posture
          <InfoHint label="About the mission risk posture">
            Policy inputs in force for every verdict in this session. They are read from the
            active screening profile — never chosen here.
          </InfoHint>
        </span>
        <dl className="flex flex-wrap items-center gap-x-6 gap-y-2 font-mono text-caption">
          {items.map((item) => (
            <div key={item.label} className="flex items-baseline gap-2">
              <Tooltip content={item.hint} align="start">
                <dt
                  tabIndex={0}
                  className="cursor-help rounded-sm text-text-3 underline decoration-border-2 decoration-dotted underline-offset-4"
                >
                  {item.label}
                </dt>
              </Tooltip>
              <dd className="text-num text-text-num tnum" data-tabular-nums="true">
                {item.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </Panel>
  );
}

function EscapeSpotlight({ escape }: { escape: EscapeHit | "none" | null }): React.JSX.Element {
  if (escape === null) {
    return (
      <Panel testId="s1-spotlight-loading">
        <div className="space-y-3 p-4" role="status" aria-label="Resolving escape spotlight">
          <Skeleton className="h-3 w-1/4" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </Panel>
    );
  }
  if (escape === "none") {
    return (
      <Panel testId="s1-spotlight-empty">
        <PanelHeader
          index="⌕"
          title="Escape spotlight"
          actions={<SeverityChip value="PASS" />}
        />
        <PanelBody>
          <p className="max-w-prose text-body text-text-2">
            No part currently satisfies the escape predicate (DPAT FAIL with absolute PASS) in
            the scanned lots. Absolute screening and lot-relative screening agree everywhere
            scanned — or the scan is still covered by the probe budget.
          </p>
        </PanelBody>
      </Panel>
    );
  }

  const facts: Array<{ label: string; value: string; tone?: "severe" }> = [
    { label: "lot", value: escape.lotId },
    { label: "parameter", value: escape.parameter },
    { label: "observed", value: `${formatPlain(escape.observed, 2)} ${escape.unit}` },
    { label: "lot-relative", value: `✗ ${formatPlain(escape.z)} σ`, tone: "severe" },
  ];
  if (escape.dpatLimitHigh !== null)
    facts.push({ label: "DPAT limit", value: `${formatPlain(escape.dpatLimitHigh)} ${escape.unit}` });
  if (escape.absoluteLimitHigh !== null)
    facts.push({
      label: "absolute limit",
      value: `${formatPlain(escape.absoluteLimitHigh)} ${escape.unit}`,
    });

  return (
    <Panel testId="s1-spotlight" tone="severe">
      <PanelHeader
        index="⌕"
        title="Escape spotlight"
        hint="The problem statement, rendered as UI: two screening methods disagreeing about one part."
        actions={
          <>
            <SeverityChip value="FAIL" />
            <SeverityChip value="PASS" />
          </>
        }
      />
      <PanelBody>
        <p className="max-w-prose text-body text-text-2">
          Conventional screening ships this part: it passes every absolute limit. Its own lot
          disagrees — a <span className="font-semibold text-text-num">latent escape</span>.
        </p>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <button
            type="button"
            onClick={() => navigate({ surface: "S3", componentId: escape.componentId })}
            className="inline-flex min-h-control-md items-center break-all rounded-sm border border-border-2 bg-surface-2 px-3 font-mono text-num text-text-num transition-colors duration-fast hover:border-text-3 hover:bg-surface-3"
            data-testid="s1-spotlight-open"
          >
            {escape.componentId}
          </button>
          <Button
            variant="quiet"
            size="sm"
            onClick={() => navigate({ surface: "S3", componentId: escape.componentId })}
          >
            Investigate →
          </Button>
        </div>

        <dl className="grid grid-cols-2 gap-x-5 gap-y-3 font-mono text-caption sm:grid-cols-3">
          {facts.map((fact) => (
            <div key={fact.label} className="min-w-0">
              <dt className="truncate text-text-3">{fact.label}</dt>
              <dd
                className={
                  fact.tone === "severe"
                    ? "mt-1 break-all text-sev-severe tnum"
                    : "mt-1 break-all text-text-num tnum"
                }
                data-tabular-nums="true"
              >
                {fact.value}
              </dd>
            </div>
          ))}
        </dl>

        <p className="max-w-prose text-caption text-text-3">
          Resolved at runtime by predicate (first DPAT-FAIL + absolute-PASS in lot order).
          Nothing here is hard-coded; re-ingest or reseed and it re-resolves.
        </p>
      </PanelBody>
    </Panel>
  );
}
