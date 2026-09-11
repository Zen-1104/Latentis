import type { ReactNode } from "react";
import { cn } from "./cn";

export type BadgeTone = "neutral" | "outline" | "synthetic" | "accent";

/**
 * Non-severity badge: counts, provenance markers, identity tags.
 *
 * Deliberately separate from `SeverityChip`. A badge must never be able to
 * imply a verdict, so it has no access to the severity tokens — only
 * neutral surfaces and the dedicated synthetic hue (INV-3).
 */
export function Badge({
  children,
  tone = "neutral",
  className,
  testId,
  mono = true,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
  testId?: string;
  mono?: boolean;
}): React.JSX.Element {
  const TONES: Readonly<Record<BadgeTone, string>> = {
    neutral: "border-border-1 bg-surface-2 text-text-2",
    outline: "border-border-2 bg-transparent text-text-3",
    synthetic: "border-synthetic bg-synthetic text-text-num font-semibold",
    accent: "border-accent bg-accent-soft text-text-num",
  };
  return (
    <span
      data-testid={testId}
      className={cn(
        "inline-flex h-chip shrink-0 items-center gap-1 whitespace-nowrap rounded-sm border px-2 text-caption",
        mono && "font-mono",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/**
 * Live status indicator. The dot is never the only carrier — the label
 * always states the status in words, which is the same rule severity
 * follows (colour is never alone).
 */
export function StatusDot({
  tone,
  pulse = false,
}: {
  tone: "nominal" | "elevated" | "severe" | "weak";
  pulse?: boolean;
}): React.JSX.Element {
  const COLORS = {
    nominal: "bg-sev-nominal",
    elevated: "bg-sev-elevated",
    severe: "bg-sev-severe",
    weak: "bg-evidence-weak",
  } as const;
  return (
    <span aria-hidden="true" className="relative inline-flex h-2 w-2 shrink-0">
      {pulse && (
        <span
          className={cn(
            "absolute inset-0 rounded-full opacity-60 motion-safe:animate-ping",
            COLORS[tone],
          )}
        />
      )}
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", COLORS[tone])} />
    </span>
  );
}

/**
 * Headline figure with its label and unit. Used for the fleet-level counts
 * on Mission Control, where the numbers are aggregates rather than traced
 * decision values — so this must not look like a `Metric`, which is
 * ledger-backed and clickable.
 */
export function StatTile({
  label,
  value,
  unit,
  hint,
  tone = "default",
  testId,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: ReactNode;
  tone?: "default" | "severe" | "nominal";
  testId?: string;
}): React.JSX.Element {
  return (
    <div
      data-testid={testId}
      className="min-w-0 rounded-md border border-border-1 bg-surface-1 px-4 py-3"
    >
      <div className="eyebrow truncate">{label}</div>
      <div className="mt-2 flex items-baseline gap-2">
        <span
          className={cn(
            "font-mono text-num-lg font-semibold tnum",
            tone === "severe"
              ? "text-sev-severe"
              : tone === "nominal"
                ? "text-sev-nominal"
                : "text-text-num",
          )}
          data-tabular-nums="true"
        >
          {value}
        </span>
        {unit !== undefined && (
          <span className="font-mono text-caption text-text-3">{unit}</span>
        )}
      </div>
      {hint !== undefined && (
        <div className="mt-1 truncate text-caption text-text-3">{hint}</div>
      )}
    </div>
  );
}
