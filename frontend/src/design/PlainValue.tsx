import { formatPlain } from "../format";

interface PlainValueProps {
  value: number;
  unit: string;
  label: string;
  precision?: number;
  testId?: string;
}

/**
 * Distinct treatment for backend plain floats on fully_traced=false blocks
 * (D-044/D-045 adapters). Marked with ≈ weak-evidence so a plain value is
 * never mistaken for a traced decision value.
 */
export function PlainValue({
  value,
  unit,
  label,
  precision = 2,
  testId,
}: PlainValueProps): React.JSX.Element {
  return (
    <span
      title={`${label} — plain backend value (provenance adapter, not a traced decision value)`}
      aria-label={`${label}: ${formatPlain(value, precision)} ${unit} (untraced adapter value)`}
      data-testid={testId !== undefined ? `plain-${testId}` : undefined}
      className="inline-flex items-baseline gap-1 font-mono text-num text-text-2 tnum"
      data-tabular-nums="true"
    >
      <span aria-hidden="true" className="text-evidence-weak">
        ≈
      </span>
      <span>{formatPlain(value, precision)}</span>
      <span className="font-mono text-caption text-text-3">{unit}</span>
    </span>
  );
}
