import type { TracedValueSchema } from "../api/generated/client";
import { formatTraced } from "../format";
import { useLedger } from "./useLedger";
import { cn } from "./ui/cn";

interface MetricProps {
  traced: TracedValueSchema;
  /** Accessible label for the value, e.g. "DPAT upper limit". */
  label: string;
  /** Test id suffix, e.g. "dpat-limit-high". */
  testId?: string;
  size?: "md" | "lg";
}

/**
 * The only permitted way to render a decision-bearing number
 * (UI_DESIGN_SYSTEM §5). Always clickable to the ledger drawer.
 */
export function Metric({ traced, label, testId, size = "md" }: MetricProps): React.JSX.Element {
  const { openLedger } = useLedger();
  const sizeClass = size === "lg" ? "text-num-lg" : "text-num";
  return (
    <button
      type="button"
      onClick={() => openLedger(traced, label)}
      title={`${label} — click to show the arithmetic`}
      aria-label={`${label}: ${formatTraced(traced)} ${traced.unit}. Activate to show the arithmetic.`}
      data-testid={testId !== undefined ? `metric-${testId}` : undefined}
      className={cn(
        "group -mx-1 inline-flex items-baseline gap-1 rounded-sm px-1 text-left",
        "transition-colors duration-fast hover:bg-hover",
      )}
    >
      <span
        className={cn(
          sizeClass,
          "font-mono text-text-num tnum",
          // The dotted underline is the affordance: every traced number is a
          // door into its own arithmetic.
          "underline decoration-border-2 decoration-dotted underline-offset-4",
          "transition-colors duration-fast group-hover:decoration-text-num",
        )}
        data-tabular-nums="true"
      >
        {formatTraced(traced)}
      </span>
      <span className="font-mono text-caption text-text-3">{traced.unit}</span>
    </button>
  );
}
