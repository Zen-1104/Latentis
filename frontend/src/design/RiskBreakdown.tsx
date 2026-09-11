import type { ReactNode } from "react";
import type { RiskBlock } from "../api/generated/client";
import { formatPlain, isTraced } from "../format";
import { Metric } from "./Metric";
import { PlainValue } from "./PlainValue";
import { FieldLabel } from "./ui/Panel";
import { cn } from "./ui/cn";

interface RiskBreakdownProps {
  risk: RiskBlock;
  testId: string;
}

/**
 * Additive risk decomposition. Components must sum to the total
 * (sum_check shipped in the payload). risk_index orders the worklist —
 * it never decides the band (ordinal note always shown).
 */
export function RiskBreakdown({ risk, testId }: RiskBreakdownProps): React.JSX.Element {
  const comps = risk.components ?? [];
  const denom = comps.reduce((m, c) => Math.max(m, Math.abs(c.weighted)), 0);
  return (
    <div data-testid={testId} className="space-y-2">
      {risk.risk_index !== undefined && risk.risk_index !== null && isTraced(risk.risk_index) && (
        <div className="rounded-sm border border-border-1 bg-surface-2 p-3">
          <FieldLabel>Risk score</FieldLabel>
          <div className="mt-1">
            <Metric
              traced={risk.risk_index}
              label="risk_index (decomposed)"
              testId="risk-total"
              size="lg"
            />
          </div>
        </div>
      )}
      <div className="space-y-2">
        {comps.map((c) => (
          <RiskRow
            key={c.name}
            name={c.name}
            weight={c.weight}
            weighted={c.weighted}
            fraction={denom > 0 ? Math.abs(c.weighted) / denom : 0}
            raw={
              c.raw !== undefined && c.raw !== null && isTraced(c.raw) ? (
                <Metric traced={c.raw} label={`risk component ${c.name}`} testId={`risk-${c.name}`} />
              ) : (
                <span className="font-mono text-caption text-text-3">raw —</span>
              )
            }
          />
        ))}
      </div>
      {risk.sum_check !== undefined && risk.sum_check !== null && (
        <div className="rounded-sm border border-border-1 bg-surface-2 p-3">
          <FieldLabel>sum check</FieldLabel>
          <p
            className="mt-1 break-words font-mono text-caption text-text-2 tnum"
            data-tabular-nums="true"
          >
            Σ {formatPlain(risk.sum_check.components_sum, 6)} vs reported{" "}
            {formatPlain(risk.sum_check.reported_total, 6)} · Δ{" "}
            {formatPlain(risk.sum_check.abs_diff, 9)} (tol{" "}
            {formatPlain(risk.sum_check.tolerance, 9)})
          </p>
        </div>
      )}
      <p className="max-w-prose text-caption text-text-3">
        This score decides the order of the worklist, nothing more — it cannot move a component
        across a verdict boundary.
      </p>
      <p className="max-w-prose font-mono text-caption text-text-3">
        {risk.ordinal_note ?? "risk_index orders the worklist; it does not decide the band"}
      </p>
    </div>
  );
}

function RiskRow({
  name,
  weight,
  weighted,
  fraction,
  raw,
}: {
  name: string;
  weight: number;
  weighted: number;
  fraction: number;
  raw: ReactNode;
}): React.JSX.Element {
  const positive = weighted >= 0;
  return (
    <div className="grid grid-cols-1 items-center gap-x-4 gap-y-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]">
      <span className="min-w-0 truncate font-mono text-caption text-text-2" title={name}>
        {name} <span className="text-text-3">×{formatPlain(weight)}</span>
      </span>
      <div
        className="h-bar overflow-hidden rounded-full bg-surface-2"
        role="img"
        aria-label={`${name} weighted contribution ${formatPlain(weighted, 4)}`}
      >
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-fast",
            positive ? "bg-sev-elevated" : "bg-sev-nominal",
          )}
          style={{ width: `${Math.max(0, Math.min(1, fraction)) * 100}%` }}
        />
      </div>
      <span className="flex flex-wrap items-center justify-end gap-2">
        {raw}
        <span
          className="font-mono text-caption text-text-3 tnum"
          data-tabular-nums="true"
        >
          {positive ? "+" : ""}
          {formatPlain(weighted, 4)}
        </span>
      </span>
    </div>
  );
}

/** Plain risk_index fallback (should not normally occur — traced by contract). */
export function RiskIndexPlain({ value }: { value: number }): React.JSX.Element {
  return <PlainValue value={value} unit="index" label="risk_index (untraced)" testId="risk-total" />;
}
