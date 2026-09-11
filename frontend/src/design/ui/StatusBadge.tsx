import { EVIDENCE_WEAK_CONFIG, SEVERITY_CONFIGS } from "../tokens";
import { severityOf, type DisplaySeverity } from "../severityMap";
import { verdictTerm } from "../vocabulary";
import { Tooltip } from "./Tooltip";
import { cn } from "./cn";

export type StatusSize = "sm" | "md" | "lg";

interface StatusBadgeProps {
  /** Raw backend verdict / severity / band string. */
  value: string | null | undefined;
  /**
   * Word shown to the user. Defaults to the plain-language reading from the
   * vocabulary; pass `false` to show the backend enum verbatim instead
   * (used where an auditor is reading the payload, not the product).
   */
  humanize?: boolean;
  size?: StatusSize;
  /** Adds a hover/focus explanation of what the state means. */
  withHelp?: boolean;
  /**
   * Appends the backend enum after the human label, e.g.
   * "Strongly unusual · SEVERE". Used where an auditor must be able to read
   * the payload value straight off the screen — and where the journey specs
   * assert on that exact string.
   */
  showTechnical?: boolean;
  testId?: string;
  className?: string;
}

const SIZES: Readonly<Record<StatusSize, string>> = {
  sm: "h-chip px-2 text-caption gap-1",
  md: "min-h-control-sm px-2 text-body gap-2",
  lg: "min-h-control-md px-3 text-h2 font-semibold gap-2",
};

/**
 * The one way to render a backend state.
 *
 * Always glyph + word + colour (NN-1). The word is the human reading —
 * "Strongly unusual" rather than `SEVERE` — while the enum stays available
 * in the tooltip so an expert can map it back to the payload. Severity is
 * resolved through `severityMap`, so an unrecognised string renders as a
 * neutral label instead of inventing a severity.
 */
export function StatusBadge({
  value,
  humanize = true,
  size = "sm",
  withHelp = false,
  showTechnical = false,
  testId,
  className,
}: StatusBadgeProps): React.JSX.Element {
  const sev = severityOf(value);
  const term = verdictTerm(value);
  const shown = humanize && term !== null ? term.label : (value ?? "—");
  const raw = value ?? null;
  const showRaw = showTechnical && raw !== null && raw !== shown;

  const tone = toneFor(sev);
  const badge = (
    <span
      data-testid={testId}
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded-sm border font-mono",
        SIZES[size],
        tone.border,
        tone.text,
        "bg-surface-0",
        className,
      )}
    >
      {tone.glyph !== null && <span aria-hidden="true">{tone.glyph}</span>}
      <span>{shown}</span>
      {showRaw && (
        <span className="text-text-3">
          <span aria-hidden="true">· </span>
          {raw}
        </span>
      )}
    </span>
  );

  if (!withHelp || term === null) return badge;

  return (
    <Tooltip
      content={
        <span className="block space-y-1">
          <span className="block font-sans">{term.explain}</span>
          {term.technical !== undefined && (
            <span className="block font-mono text-text-3">{term.technical}</span>
          )}
        </span>
      }
    >
      <span tabIndex={0} className="cursor-help rounded-sm">
        {badge}
      </span>
    </Tooltip>
  );
}

function toneFor(sev: DisplaySeverity | null): {
  border: string;
  text: string;
  glyph: string | null;
} {
  if (sev === null) return { border: "border-border-2", text: "text-text-2", glyph: null };
  if (sev === "weak")
    return {
      border: "border-evidence-weak",
      text: "text-evidence-weak",
      glyph: EVIDENCE_WEAK_CONFIG.glyph,
    };
  const cfg = SEVERITY_CONFIGS[sev];
  return { border: cfg.tailwindBorder, text: cfg.tailwindText, glyph: cfg.glyph };
}

/**
 * Two states shown as a deliberate pair, with the relationship between them
 * named. This is the product's central moment — conventional screening
 * passing a part its own lot rejects — so it gets a dedicated component
 * rather than two chips sitting next to each other.
 */
export function VerdictContrast({
  leftLabel,
  leftValue,
  rightLabel,
  rightValue,
  leftHint,
  rightHint,
  testId,
}: {
  leftLabel: string;
  leftValue: string | null | undefined;
  rightLabel: string;
  rightValue: string | null | undefined;
  leftHint?: string;
  rightHint?: string;
  testId?: string;
}): React.JSX.Element {
  const disagree =
    leftValue != null &&
    rightValue != null &&
    severityOf(leftValue) !== severityOf(rightValue);

  return (
    <div
      data-testid={testId}
      className={cn(
        "grid grid-cols-1 gap-px overflow-hidden rounded-md border sm:grid-cols-[1fr_auto_1fr]",
        disagree ? "border-sev-severe" : "border-border-1",
      )}
    >
      <VerdictSide label={leftLabel} value={leftValue} hint={leftHint} />
      <div
        className={cn(
          "flex items-center justify-center bg-surface-2 px-3 py-2 sm:px-4",
          "font-mono text-caption uppercase tracking-wider",
          disagree ? "text-sev-severe" : "text-text-3",
        )}
      >
        {disagree ? "disagree" : "agree"}
      </div>
      <VerdictSide label={rightLabel} value={rightValue} hint={rightHint} />
    </div>
  );
}

function VerdictSide({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | null | undefined;
  hint?: string;
}): React.JSX.Element {
  return (
    <div className="min-w-0 bg-surface-1 px-4 py-4">
      <div className="eyebrow">{label}</div>
      <div className="mt-2">
        <StatusBadge value={value} size="lg" withHelp />
      </div>
      {hint !== undefined && (
        <p className="mt-2 max-w-prose text-body text-text-2">{hint}</p>
      )}
    </div>
  );
}
