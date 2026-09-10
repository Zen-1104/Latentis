import type { ReactNode } from "react";
import { cn } from "./cn";
import { Panel } from "./Panel";

/**
 * Skeleton block. One shimmer sweep from the shared `.skeleton` rule rather
 * than `animate-pulse` on every child, which made whole panels breathe.
 */
export function Skeleton({
  className,
  rounded = "sm",
}: {
  className?: string;
  rounded?: "sm" | "md" | "full";
}): React.JSX.Element {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "skeleton h-4",
        rounded === "full" ? "rounded-full" : rounded === "md" ? "rounded-md" : "rounded-sm",
        className,
      )}
    />
  );
}

/**
 * Loading placeholder shaped like the content it replaces, so the layout
 * does not jump when data lands.
 */
export function SkeletonPanel({
  rows = 3,
  withHeader = true,
  testId,
  label = "Loading",
}: {
  rows?: number;
  withHeader?: boolean;
  testId?: string;
  label?: string;
}): React.JSX.Element {
  return (
    <div
      data-testid={testId}
      role="status"
      aria-live="polite"
      aria-label={label}
      className="space-y-3"
    >
      {withHeader && (
        <div className="flex items-center gap-3">
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      )}
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton
          key={i}
          className={cn("h-4", i % 3 === 0 ? "w-full" : i % 3 === 1 ? "w-3/4" : "w-1/2")}
        />
      ))}
      <span className="sr-only">{label}</span>
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  /** Call to action — usually a single primary Button. */
  action?: ReactNode;
  /** Decorative glyph from the locked set. */
  glyph?: string;
  testId?: string;
  className?: string;
}

/**
 * Designed empty state. "No data." was a grey sentence; an empty surface
 * has to say what is missing and what the operator can do next.
 */
export function EmptyState({
  title,
  description,
  action,
  glyph = "⌕",
  testId,
  className,
}: EmptyStateProps): React.JSX.Element {
  return (
    <Panel testId={testId} className={cn("px-6 py-8", className)}>
      <div className="mx-auto max-w-prose space-y-3 text-center">
        <span
          aria-hidden="true"
          className="mx-auto flex h-cell w-cell items-center justify-center rounded-full border border-border-1 bg-surface-2 font-mono text-h2 text-text-3"
        >
          {glyph}
        </span>
        <h2 className="text-h2 font-semibold text-text-1">{title}</h2>
        {description !== undefined && (
          <div className="text-body text-text-2">{description}</div>
        )}
        {action !== undefined && <div className="flex justify-center pt-1">{action}</div>}
      </div>
    </Panel>
  );
}

/**
 * Inline non-blocking notice. `role` is chosen by tone: a failure is an
 * alert, everything else is a polite status.
 */
export function Notice({
  tone,
  children,
  glyph,
  testId,
  className,
}: {
  tone: "error" | "weak" | "success" | "info";
  children: ReactNode;
  glyph?: string;
  testId?: string;
  className?: string;
}): React.JSX.Element {
  const TONE = {
    error: { border: "border-sev-severe", text: "text-sev-severe", glyph: "✗" },
    weak: { border: "border-evidence-weak", text: "text-evidence-weak", glyph: "≈" },
    success: { border: "border-sev-nominal", text: "text-sev-nominal", glyph: "✓" },
    info: { border: "border-border-2", text: "text-text-3", glyph: "·" },
  }[tone];

  return (
    <div
      data-testid={testId}
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "flex items-start gap-3 rounded-md border bg-surface-1 px-3 py-3 text-body text-text-1",
        TONE.border,
        className,
      )}
    >
      <span aria-hidden="true" className={cn("mt-px font-mono leading-tight", TONE.text)}>
        {glyph ?? TONE.glyph}
      </span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
