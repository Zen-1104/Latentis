import { formatPlain } from "../format";
import { DataTable } from "./DataTable";

export interface DriftObserved {
  h: number;
  value: number;
  status: string;
}

interface DriftChartProps {
  observed: DriftObserved[];
  /** Backend 168 h point forecast (endpoint; connector is schematic). */
  forecast168: number | null;
  /** Naïve linear baseline at 168 h (endpoint). */
  baseline168: number | null;
  /** One-sided conformal upper bound at 168 h. */
  bound168: number | null;
  absHigh: number | null;
  /** Safety-slope line origin + gradient (both backend values). */
  safety: { v0: number; slope: number } | null;
  horizon: number;
  unit: string;
  testId: string;
}

const W = 640;
const H = 300;
const PADL = 56;
const PADR = 16;
const PADT = 14;
const PADB = 30;

/**
 * Forecast chart (UX_SPEC §4). Observed markers are measurements; the 168 h
 * endpoints (forecast, baseline, bound) are backend values. The forecast
 * connector is dashed-schematic — only the endpoints are authoritative.
 */
export function DriftChart({
  observed,
  forecast168,
  baseline168,
  bound168,
  absHigh,
  safety,
  horizon,
  unit,
  testId,
}: DriftChartProps): React.JSX.Element {
  const obs = observed.filter((o) => Number.isFinite(o.value));
  const last: DriftObserved | null = obs.length > 0 ? (obs[obs.length - 1] as DriftObserved) : null;
  const ys = [
    ...obs.map((o) => o.value),
    forecast168,
    baseline168,
    bound168,
    absHigh,
    safety?.v0 ?? null,
  ].filter((v): v is number => v !== null && Number.isFinite(v));
  const lo = ys.length > 0 ? Math.min(...ys) : 0;
  const hiRaw = ys.length > 0 ? Math.max(...ys) : 1;
  const pad = (hiRaw - lo) * 0.08 || 1;
  const hi = hiRaw + pad;
  const xMax = horizon > 0 ? horizon : 168;
  const x = (h: number): number => PADL + (h / xMax) * (W - PADL - PADR);
  const y = (v: number): number => PADT + (1 - (v - lo) / (hi - lo)) * (H - PADT - PADB);
  const lastH = last?.h ?? 24;

  const bandPath =
    last !== null && forecast168 !== null && bound168 !== null
      ? `M ${x(lastH)} ${y(forecast168)} L ${x(xMax)} ${y(forecast168)} L ${x(xMax)} ${y(bound168)} L ${x(lastH)} ${y(bound168)} Z`
      : null;

  return (
    <div data-testid={testId}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full rounded-md border border-border-1 bg-surface-1"
        role="img"
        aria-label={`Drift forecast in ${unit} over 0 to ${xMax} hours.`}
      >
        {[0.25, 0.5, 0.75].map((f) => (
          <line
            key={f}
            x1={PADL}
            x2={W - PADR}
            y1={PADT + f * (H - PADT - PADB)}
            y2={PADT + f * (H - PADT - PADB)}
            stroke="var(--border-1)"
            strokeWidth={1}
          />
        ))}
        {absHigh !== null && Number.isFinite(absHigh) && (
          <line
            x1={PADL}
            x2={W - PADR}
            y1={y(absHigh)}
            y2={y(absHigh)}
            stroke="var(--sev-critical)"
            strokeWidth={1.5}
          />
        )}
        {safety !== null && (
          <line
            x1={x(0)}
            x2={x(xMax)}
            y1={y(safety.v0)}
            y2={y(safety.v0 + safety.slope * xMax)}
            stroke="var(--text-3)"
            strokeWidth={1}
            strokeDasharray="3 3"
          />
        )}
        {bandPath !== null && <path d={bandPath} fill="var(--bound-fill)" />}
        {last !== null && baseline168 !== null && (
          <line
            x1={x(lastH)}
            x2={x(xMax)}
            y1={y(last.value)}
            y2={y(baseline168)}
            stroke="var(--baseline)"
            strokeWidth={1.5}
            strokeDasharray="5 4"
          />
        )}
        {last !== null && forecast168 !== null && (
          <line
            x1={x(lastH)}
            x2={x(xMax)}
            y1={y(last.value)}
            y2={y(forecast168)}
            stroke="var(--sev-nominal)"
            strokeWidth={2}
            strokeDasharray="6 3"
          />
        )}
        {obs.map((o) => (
          <circle key={o.h} cx={x(o.h)} cy={y(o.value)} r={4.5} fill="var(--text-num)">
            <title>{`${o.h} h: ${formatPlain(o.value, 3)} ${unit} (${o.status})`}</title>
          </circle>
        ))}
        <text x={PADL} y={H - 12} fill="var(--text-3)" fontSize={10} fontFamily="monospace">
          0 h
        </text>
        <text x={x(24)} y={H - 12} fill="var(--text-3)" fontSize={10} fontFamily="monospace">
          24 h
        </text>
        <text
          x={W - PADR}
          y={H - 12}
          fill="var(--text-3)"
          fontSize={10}
          fontFamily="monospace"
          textAnchor="end"
        >
          {xMax} h
        </text>
        {/* Axis labels are clamped into the viewBox: at the extremes the text
            baseline would otherwise fall outside it and the value vanish. */}
        <text
          x={6}
          y={Math.max(y(hi - pad), PADT + 8)}
          fill="var(--text-3)"
          fontSize={10}
          fontFamily="monospace"
        >
          {formatPlain(hi - pad, 1)}
        </text>
        <text
          x={6}
          y={Math.min(y((hi - pad + lo) / 2), H - PADB - 4)}
          fill="var(--text-3)"
          fontSize={10}
          fontFamily="monospace"
        >
          {formatPlain((hi - pad + lo) / 2, 1)}
        </text>
        <text
          x={6}
          y={Math.min(y(lo), H - PADB - 4)}
          fill="var(--text-3)"
          fontSize={10}
          fontFamily="monospace"
        >
          {formatPlain(lo, 1)}
        </text>
      </svg>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-2 border-t border-border-1 pt-3 font-mono text-caption text-text-3">
        <li>
          <span className="text-text-num" aria-hidden="true">
            ●
          </span>{" "}
          Observed (only observations)
        </li>
        <li>
          <span className="text-sev-nominal" aria-hidden="true">
            ┄
          </span>{" "}
          Forecast segment → 168 h endpoint
        </li>
        <li>
          <span className="text-baseline" aria-hidden="true">
            ┄
          </span>{" "}
          Naïve linear baseline
        </li>
        <li>
          <span className="text-sev-critical" aria-hidden="true">
            ──
          </span>{" "}
          Absolute limit
        </li>
      </ul>
      <div className="mt-3">
        <DataTable
          testId={`${testId}-table`}
          caption={`Forecast values in ${unit} — same endpoints as plotted`}
          columns={[
            { header: "Series", render: (r) => r.series },
            { header: "t (h)", numeric: true, render: (r) => r.h },
            { header: "Value", numeric: true, render: (r) => r.display },
          ]}
          rows={buildRows(obs, forecast168, baseline168, bound168, unit)}
          keyOf={(r) => `${r.series}-${r.h}`}
        />
      </div>
    </div>
  );
}

interface DriftRow {
  series: string;
  h: string;
  display: string;
}

function buildRows(
  obs: DriftObserved[],
  forecast168: number | null,
  baseline168: number | null,
  bound168: number | null,
  unit: string,
): DriftRow[] {
  const rows: DriftRow[] = obs.map((o) => ({
    series: `Observed (${o.status})`,
    h: String(o.h),
    display: `${formatPlain(o.value, 3)} ${unit}`,
  }));
  if (forecast168 !== null)
    rows.push({ series: "Forecast point", h: "168", display: `${formatPlain(forecast168, 3)} ${unit}` });
  if (bound168 !== null)
    rows.push({ series: "Conformal upper bound", h: "168", display: `${formatPlain(bound168, 3)} ${unit}` });
  if (baseline168 !== null)
    rows.push({ series: "Linear baseline", h: "168", display: `${formatPlain(baseline168, 3)} ${unit}` });
  return rows;
}
