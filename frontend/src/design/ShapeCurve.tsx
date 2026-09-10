import { DataTable } from "./DataTable";
import { formatPlain } from "../format";

export interface ShapePoint {
  t_hours: number;
  phi: number;
}

/** Fitted population shape curve (backend points plotted directly, no arithmetic). */
export function ShapeCurve({ points, testId }: { points: ShapePoint[]; testId: string }): React.JSX.Element {
  const W = 640;
  const H = 220;
  const PADL = 56;
  const PADR = 16;
  const PADT = 14;
  const PADB = 30;
  const maxT = Math.max(...points.map((p) => p.t_hours), 168);
  const maxPhi = Math.max(...points.map((p) => p.phi), 1) * 1.1;
  const x = (t: number): number => PADL + (t / maxT) * (W - PADL - PADR);
  const y = (phi: number): number => PADT + (1 - phi / maxPhi) * (H - PADT - PADB);
  const d = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${x(p.t_hours).toFixed(1)} ${y(p.phi).toFixed(1)}`)
    .join(" ");
  return (
    <div data-testid={testId}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full rounded-md border border-border-1 bg-surface-1"
        role="img"
        aria-label="Fitted population shape curve."
      >
        <path d={d} fill="none" stroke="var(--sev-nominal)" strokeWidth={2} />
        {points.map((p) => (
          <circle key={p.t_hours} cx={x(p.t_hours)} cy={y(p.phi)} r={3.5} fill="var(--text-num)">
            <title>{`${p.t_hours} h: Φ = ${formatPlain(p.phi, 4)}`}</title>
          </circle>
        ))}
        <text x={PADL} y={H - 12} fill="var(--text-3)" fontSize={10} fontFamily="monospace">0 h</text>
        <text x={W - PADR} y={H - 12} fill="var(--text-3)" fontSize={10} fontFamily="monospace" textAnchor="end">
          {maxT} h
        </text>
        {/* Clamped into the viewBox — see DriftChart. */}
        <text
          x={6}
          y={Math.max(y(maxPhi / 1.1), PADT + 8)}
          fill="var(--text-3)"
          fontSize={10}
          fontFamily="monospace"
        >
          {formatPlain(maxPhi / 1.1, 2)}
        </text>
        <text
          x={6}
          y={Math.min(y(0), H - PADB - 4)}
          fill="var(--text-3)"
          fontSize={10}
          fontFamily="monospace"
        >
          0.00
        </text>
      </svg>
      <div className="mt-3">
        <DataTable
          testId={`${testId}-table`}
          caption="Fitted shape points (backend values)"
          columns={[
            { header: "t (h)", numeric: true, render: (r) => formatPlain(r.t_hours, 1) },
            { header: "Φ", numeric: true, render: (r) => formatPlain(r.phi, 4) },
          ]}
          rows={points}
          keyOf={(r) => String(r.t_hours)}
        />
      </div>
    </div>
  );
}
