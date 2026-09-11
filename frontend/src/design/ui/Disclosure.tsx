import type { ReactNode } from "react";
import { cn } from "./cn";

interface TechnicalDetailsProps {
  /** What the reader gets by opening it, e.g. "Technical details". */
  label?: string;
  /** Short note on what is inside, shown beside the label. */
  hint?: string;
  children: ReactNode;
  /** Open on first render — for sections an expert reads every time. */
  defaultOpen?: boolean;
  testId?: string;
  className?: string;
}

/**
 * The progressive-disclosure primitive (Phase 23).
 *
 * Nothing is deleted to simplify a screen — it is moved in here. The
 * default view answers the reader's practical question; opening this
 * reveals the payload-level evidence an auditor needs. Uses a native
 * `<details>` so it works without JavaScript, keeps its content in the
 * accessibility tree, and is findable by in-page search.
 */
export function TechnicalDetails({
  label = "Technical details",
  hint,
  children,
  defaultOpen = false,
  testId,
  className,
}: TechnicalDetailsProps): React.JSX.Element {
  return (
    <details
      data-testid={testId}
      open={defaultOpen}
      className={cn(
        "group rounded-md border border-border-1 bg-surface-1",
        "[&[open]]:bg-surface-1",
        className,
      )}
    >
      <summary
        className={cn(
          "flex min-h-control-md cursor-pointer list-none items-center gap-2 px-4",
          "transition-colors duration-fast hover:bg-hover",
          "[@media(pointer:coarse)]:min-h-touch",
        )}
      >
        <span
          aria-hidden="true"
          className="font-mono text-caption text-text-3 transition-transform duration-fast group-open:rotate-90"
        >
          ›
        </span>
        <span className="eyebrow">{label}</span>
        {hint !== undefined && (
          <span className="truncate text-caption text-text-3">· {hint}</span>
        )}
      </summary>
      <div className="space-y-4 border-t border-border-1 p-4">{children}</div>
    </details>
  );
}

/**
 * Plain-English section heading.
 *
 * The title is written as the question the section answers, so a reader
 * scanning the page learns the structure of the argument rather than a list
 * of subsystem names.
 */
export function SectionHeader({
  title,
  hint,
  actions,
  level = 2,
  size,
  id,
  className,
}: {
  title: ReactNode;
  hint?: ReactNode;
  actions?: ReactNode;
  /**
   * Heading level. Semantic only — a page section directly under the page
   * title must be an h2 even when it is visually quiet, or the document
   * outline skips a level.
   */
  level?: 2 | 3;
  /** Visual weight, independent of the semantic level. */
  size?: "lg" | "sm";
  id?: string;
  className?: string;
}): React.JSX.Element {
  const Heading = level === 2 ? "h2" : "h3";
  const visual = size ?? (level === 2 ? "lg" : "sm");
  return (
    <div
      className={cn(
        "flex flex-wrap items-end justify-between gap-x-6 gap-y-2",
        className,
      )}
    >
      <div className="min-w-0">
        <Heading
          id={id}
          className={cn(
            "font-semibold tracking-tight text-text-1",
            visual === "lg" ? "text-h1" : "text-h2",
          )}
        >
          {title}
        </Heading>
        {hint !== undefined && (
          <p className="mt-1 max-w-prose text-body leading-relaxed text-text-2">{hint}</p>
        )}
      </div>
      {actions !== undefined && (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      )}
    </div>
  );
}

/**
 * The one-sentence reading of a visualisation or table sitting above it.
 *
 * Phase 20 asks every important visual to carry its takeaway. The text is
 * always derived from values the backend returned — callers compose it from
 * payload data, never from an assumption about what the data "probably"
 * says.
 */
export function KeyTakeaway({
  children,
  tone = "info",
  testId,
}: {
  children: ReactNode;
  tone?: "info" | "severe" | "nominal" | "weak";
  testId?: string;
}): React.JSX.Element {
  const TONES = {
    info: { rule: "bg-info", label: "text-info" },
    severe: { rule: "bg-sev-severe", label: "text-sev-severe" },
    nominal: { rule: "bg-sev-nominal", label: "text-sev-nominal" },
    weak: { rule: "bg-evidence-weak", label: "text-evidence-weak" },
  }[tone];

  return (
    <div
      data-testid={testId}
      className="flex gap-3 rounded-md border border-border-1 bg-surface-2 p-3"
    >
      <span aria-hidden="true" className={cn("w-px shrink-0 rounded-full", TONES.rule)} />
      <div className="min-w-0">
        <div className={cn("eyebrow", TONES.label)}>Key takeaway</div>
        <p className="mt-1 max-w-prose text-body text-text-1">{children}</p>
      </div>
    </div>
  );
}

/**
 * A framed visualisation: human title, one-line purpose, the chart, an
 * optional legend and takeaway, and the accessible table underneath.
 *
 * Phase 25 requires every chart to state the question it answers. Wrapping
 * that in one component stops each chart from inventing its own header.
 */
export function ChartFrame({
  title,
  purpose,
  technical,
  children,
  legend,
  takeaway,
  fallback,
  testId,
}: {
  /** Written as the question the chart answers. */
  title: string;
  /** One line on how to read it. */
  purpose?: string;
  /** The technical name of what is plotted, for experts. */
  technical?: string;
  children: ReactNode;
  legend?: ReactNode;
  takeaway?: ReactNode;
  /** Accessible data table — required for every chart (RT-012). */
  fallback?: ReactNode;
  testId?: string;
}): React.JSX.Element {
  return (
    <figure data-testid={testId} className="m-0 space-y-3">
      <figcaption className="space-y-1">
        <h3 className="text-h2 font-semibold text-text-1">{title}</h3>
        {purpose !== undefined && (
          <p className="max-w-prose text-body text-text-2">{purpose}</p>
        )}
        {technical !== undefined && (
          <p className="font-mono text-caption text-text-3">{technical}</p>
        )}
      </figcaption>
      {children}
      {legend}
      {takeaway}
      {fallback !== undefined && (
        <TechnicalDetails label="Data behind this chart" hint="same values, as a table">
          {fallback}
        </TechnicalDetails>
      )}
    </figure>
  );
}
