import { EVIDENCE_WEAK_CONFIG, GUARD_VOID_CONFIG, SEVERITY_CONFIGS } from "./tokens";
import { severityOf } from "./severityMap";
import { cn } from "./ui/cn";

interface SeverityChipProps {
  /** Backend verdict / severity / band string. */
  value: string | null | undefined;
  testId?: string;
  className?: string;
}

/**
 * Glyph + text + token colour. Never colour alone (NN-1 / TEST-A11Y-001).
 *
 * The glyph is `aria-hidden` and the label carries the meaning, so the chip
 * reads correctly to a screen reader without announcing punctuation.
 */
const CHIP_BASE = cn(
  "inline-flex h-chip shrink-0 items-center gap-1 rounded-sm border px-2",
  "font-mono text-caption whitespace-nowrap",
);

export function SeverityChip({ value, testId, className }: SeverityChipProps): React.JSX.Element {
  const label = value ?? "—";
  const sev = severityOf(value);
  if (sev === null) {
    return (
      <span
        data-testid={testId}
        className={cn(CHIP_BASE, "border-border-2 bg-surface-0 text-text-2", className)}
      >
        {label}
      </span>
    );
  }
  if (sev === "weak") {
    return (
      <span
        data-testid={testId}
        className={cn(
          CHIP_BASE,
          "border-evidence-weak bg-surface-0 text-evidence-weak",
          className,
        )}
      >
        <span aria-hidden="true">{EVIDENCE_WEAK_CONFIG.glyph}</span>
        <span>{label}</span>
      </span>
    );
  }
  const cfg = SEVERITY_CONFIGS[sev];
  return (
    <span
      data-testid={testId}
      className={cn(CHIP_BASE, "bg-surface-0", cfg.tailwindBorder, cfg.tailwindText, className)}
    >
      <span aria-hidden="true">{cfg.glyph}</span>
      <span>{label}</span>
    </span>
  );
}

export function GuardVoidChip({ label }: { label: string }): React.JSX.Element {
  return (
    <span className={cn(CHIP_BASE, "border-guard-void bg-surface-0 text-guard-void")}>
      <span aria-hidden="true">{GUARD_VOID_CONFIG.glyph}</span>
      <span>{label}</span>
    </span>
  );
}
