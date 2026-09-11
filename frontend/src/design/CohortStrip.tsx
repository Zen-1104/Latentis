import { formatPlain } from "../format";
import { DataTable } from "./DataTable";

export interface StripMember {
  component_id: string;
  value: number;
  z: number;
  flagged: boolean;
}

interface CohortStripProps {
  members: StripMember[];
  focusId: string;
  limitLow: number | null;
  limitHigh: number | null;
  median: number | null;
  absHigh: number | null;
  unit: string;
  testId: string;
}

const W = 640;
const H = 132;
const PAD = 44;

/**
 * Strip plot of lot values with the peer limits as rules and the part under
 * test marked. Member positions are backend display aggregation; limits and
 * median are traced values passed as plain endpoints for plotting.
 */
export function CohortStrip({
  members,
  focusId,
  limitLow,
  limitHigh,
  median,
  absHigh,
  unit,
  testId,
}: CohortStripProps): React.JSX.Element {
  const vals = members.map((m) => m.value);
  const guides = [limitLow, limitHigh, median, absHigh].filter(
    (v): v is number => v !== null && Number.isFinite(v),
  );
  const all = [...vals, ...guides];
  const lo = all.length > 0 ? Math.min(...all) : 0;
  const hi = all.length > 0 ? Math.max(...all) : 1;
  const span = hi - lo === 0 ? 1 : hi - lo;
  const x = (v: number): number => PAD + ((v - lo) / span) * (W - PAD * 2);
  // Deterministic lane assignment (stable order, no randomness).
  const lane = (i: number): number => 22 + ((i * 37) % 72);

  return (
    <div data-testid={testId}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full rounded-md border border-border-1 bg-surface-1"
        role="img"
        aria-label={`Distribution of ${members.length} components in this lot, in ${unit}, with the peer limits drawn. The table below lists the same values.`}
      >
        {median !== null && Number.isFinite(median) && (
          <line
            x1={x(median)}
            x2={x(median)}
            y1={8}
            y2={H - 24}
            stroke="var(--text-3)"
            strokeDasharray="2 3"
          />
        )}
        {limitLow !== null && Number.isFinite(limitLow) && (
          <line
            x1={x(limitLow)}
            x2={x(limitLow)}
            y1={8}
            y2={H - 24}
            stroke="var(--sev-nominal)"
            strokeWidth={1.5}
          />
        )}
        {limitHigh !== null && Number.isFinite(limitHigh) && (
          <line
            x1={x(limitHigh)}
            x2={x(limitHigh)}
            y1={8}
            y2={H - 24}
            stroke="var(--sev-nominal)"
            strokeWidth={1.5}
          />
        )}
        {absHigh !== null && Number.isFinite(absHigh) && (
          <line
            x1={x(absHigh)}
            x2={x(absHigh)}
            y1={8}
            y2={H - 24}
            stroke="var(--sev-critical)"
            strokeWidth={1.5}
          />
        )}
        {members.map((m, i) => {
          const isFocus = m.component_id === focusId;
          return (
            <circle
              key={m.component_id}
              cx={x(m.value)}
              cy={lane(i)}
              r={isFocus ? 6 : 3}
              fill={m.flagged ? "var(--sev-severe)" : "var(--text-3)"}
              stroke={isFocus ? "var(--text-num)" : "none"}
              strokeWidth={isFocus ? 2 : 0}
            >
              <title>{`${m.component_id}: ${formatPlain(m.value)} ${unit}, ${formatPlain(m.z)} σ from its peers${m.flagged ? " — needs attention" : ""}`}</title>
            </circle>
          );
        })}
        <text x={PAD} y={H - 8} fill="var(--text-3)" fontSize={10} fontFamily="monospace">
          {formatPlain(lo)} {unit}
        </text>
        <text
          x={W - PAD}
          y={H - 8}
          fill="var(--text-3)"
          fontSize={10}
          fontFamily="monospace"
          textAnchor="end"
        >
          {formatPlain(hi)} {unit}
        </text>
      </svg>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-2 border-t border-border-1 pt-3 font-mono text-caption text-text-3">
        <li>
          <span className="text-sev-nominal" aria-hidden="true">
            ──
          </span>{" "}
          Peer limits
        </li>
        <li>
          <span className="text-sev-critical" aria-hidden="true">
            ──
          </span>{" "}
          Fixed limit
        </li>
        <li>
          <span className="text-sev-severe" aria-hidden="true">
            ●
          </span>{" "}
          Needs attention
        </li>
        <li>
          <span className="text-text-num" aria-hidden="true">
            ○
          </span>{" "}
          Part under test
        </li>
      </ul>
      <div className="mt-3">
        <DataTable
          testId={`${testId}-table`}
          maxBodyHeight
          caption={`Cohort members in ${unit} — same values as plotted`}
          columns={[
            {
              header: "Component",
              rowHeader: true,
              sortValue: (r) => r.component_id,
              render: (r) => <span className="font-mono text-text-num">{r.component_id}</span>,
            },
            {
              header: "Observed",
              numeric: true,
              sortValue: (r) => r.value,
              render: (r) => formatPlain(r.value, 3),
            },
            {
              header: "Distance from peers",
              numeric: true,
              sortValue: (r) => r.z,
              render: (r) => `${formatPlain(r.z)} σ`,
            },
            {
              header: "Signal",
              sortValue: (r) => (r.flagged ? 1 : 0),
              render: (r) =>
                r.flagged ? (
                  <span className="text-sev-severe">
                    <span aria-hidden="true">✗</span> yes
                  </span>
                ) : (
                  <span className="text-text-3">—</span>
                ),
            },
          ]}
          rows={[...members].sort((a, b) => (a.component_id < b.component_id ? -1 : 1))}
          keyOf={(r) => r.component_id}
        />
      </div>
    </div>
  );
}
