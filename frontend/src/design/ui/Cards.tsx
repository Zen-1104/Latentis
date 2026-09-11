import type { ReactNode } from "react";
import { concept, settingTerm, type Term } from "../vocabulary";
import { Tooltip } from "./Tooltip";
import { cn } from "./cn";

/**
 * A "?" affordance bound to a vocabulary entry.
 *
 * Every unfamiliar term in the product should be explainable at the point
 * of use (Phase 10), and the explanation should live in one place rather
 * than being retyped per screen. Pass a `CONCEPTS` or `SETTINGS` key and the
 * copy follows automatically.
 */
export function TermHelp({
  term,
  concept: conceptKey,
  setting,
  label,
}: {
  /** An explicit term, when it is not in the shared vocabulary. */
  term?: Term;
  /** Key into CONCEPTS. */
  concept?: string;
  /** Key into SETTINGS. */
  setting?: string;
  /** Accessible name; defaults to the term's label. */
  label?: string;
}): React.JSX.Element | null {
  const resolved =
    term ??
    (conceptKey !== undefined ? concept(conceptKey) : null) ??
    (setting !== undefined ? settingTerm(setting) : null);
  if (resolved === null) return null;

  return (
    <Tooltip
      content={
        <span className="block space-y-1">
          <span className="block font-sans font-medium text-text-1">{resolved.label}</span>
          <span className="block font-sans">{resolved.explain}</span>
          {resolved.detail !== undefined && (
            <span className="block font-sans text-text-3">{resolved.detail}</span>
          )}
          {resolved.technical !== undefined && (
            <span className="block font-mono text-text-3">{resolved.technical}</span>
          )}
        </span>
      }
    >
      <button
        type="button"
        aria-label={`What does ${label ?? resolved.label} mean?`}
        className={cn(
          "inline-flex h-chip w-chip shrink-0 items-center justify-center rounded-full",
          "border border-border-1 bg-surface-2 font-mono text-caption text-text-3",
          "transition-colors duration-fast hover:border-accent hover:text-accent-hi",
          // 22px is under the 24px minimum for a pointer target (WCAG 2.5.8).
          "[@media(pointer:coarse)]:min-h-touch [@media(pointer:coarse)]:min-w-touch",
        )}
      >
        <span aria-hidden="true">?</span>
      </button>
    </Tooltip>
  );
}

/**
 * A labelled figure with its meaning attached.
 *
 * Replaces the `alpha 0.1000 k 6.0000` style strip: the human label leads,
 * the value is typographically dominant, the unit is subordinate, and the
 * technical name is available without cluttering the face of the card.
 */
export function MetricCard({
  label,
  value,
  unit,
  hint,
  conceptKey,
  settingKey,
  technical,
  tone = "default",
  emphasis = "normal",
  action,
  testId,
  className,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: ReactNode;
  conceptKey?: string;
  settingKey?: string;
  /** Shown small and monospaced beneath the value. */
  technical?: string;
  tone?: "default" | "severe" | "nominal" | "elevated" | "info";
  emphasis?: "normal" | "hero";
  action?: ReactNode;
  testId?: string;
  className?: string;
}): React.JSX.Element {
  const TONES = {
    default: "text-text-num",
    severe: "text-sev-severe",
    nominal: "text-sev-nominal",
    elevated: "text-sev-elevated",
    info: "text-info",
  } as const;

  return (
    <div
      data-testid={testId}
      className={cn(
        "flex min-w-0 flex-col rounded-md border border-border-1 bg-surface-1 p-4",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <span className="eyebrow min-w-0 flex-1">{label}</span>
        <TermHelp concept={conceptKey} setting={settingKey} label={label} />
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span
          className={cn(
            "font-mono font-semibold tnum",
            emphasis === "hero" ? "text-display" : "text-num-lg",
            TONES[tone],
          )}
          data-tabular-nums="true"
        >
          {value}
        </span>
        {unit !== undefined && (
          <span className="font-mono text-caption text-text-3">{unit}</span>
        )}
      </div>
      {hint !== undefined && <p className="mt-1 text-caption text-text-3">{hint}</p>}
      {technical !== undefined && (
        <p className="mt-2 break-all font-mono text-caption text-text-3">{technical}</p>
      )}
      {action !== undefined && <div className="mt-3">{action}</div>}
    </div>
  );
}

/**
 * A finding stated in prose, with the evidence beside it and one clear
 * next step.
 *
 * The product's job on the landing surface is to say what happened and what
 * to do about it. That is a paragraph and a button, not a grid of numbers —
 * so this is deliberately narrative rather than tabular.
 */
export function InsightCard({
  eyebrow,
  title,
  body,
  facts,
  action,
  tone = "default",
  testId,
}: {
  eyebrow?: string;
  title: ReactNode;
  body?: ReactNode;
  /** Supporting values, rendered as a definition list. */
  facts?: Array<{ label: string; value: ReactNode; tone?: "severe" | "info" }>;
  action?: ReactNode;
  tone?: "default" | "severe" | "nominal" | "info";
  testId?: string;
}): React.JSX.Element {
  const BORDER = {
    default: "border-border-1",
    severe: "border-sev-severe",
    nominal: "border-sev-nominal",
    info: "border-info",
  }[tone];
  const hasFacts = facts !== undefined && facts.length > 0;

  return (
    <section
      data-testid={testId}
      className={cn("overflow-hidden rounded-md border bg-surface-1 shadow-panel", BORDER)}
    >
      <div className="p-5 lg:p-6">
        <div className="space-y-2">
          {eyebrow !== undefined && (
            <p
              className={cn(
                "eyebrow font-semibold",
                tone === "severe" && "text-sev-severe",
                tone === "info" && "text-info",
                tone === "nominal" && "text-sev-nominal",
              )}
            >
              {eyebrow}
            </p>
          )}
          <h2 className="text-h1 font-semibold tracking-tight text-text-1">{title}</h2>
        </div>

        {/* Claim on the left, the evidence for it on the right. */}
        <div
          className={cn(
            "mt-5 grid gap-x-8 gap-y-5",
            hasFacts ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]" : "grid-cols-1",
          )}
        >
          {body !== undefined && (
            <div className="prose-body text-body text-text-2">{body}</div>
          )}
          {hasFacts && (
            <dl
              className={cn(
                "grid grid-cols-2 gap-x-5 gap-y-4 self-start sm:grid-cols-3",
                "lg:grid-cols-1 lg:gap-y-3 lg:border-l lg:border-border-1 lg:pl-6",
              )}
            >
              {(facts ?? []).map((f) => (
                <div key={f.label} className="min-w-0 lg:flex lg:items-baseline lg:gap-3">
                  <dt className="eyebrow truncate lg:w-label lg:shrink-0 lg:overflow-visible lg:whitespace-normal">
                    {f.label}
                  </dt>
                  <dd
                    className={cn(
                      "mt-1 break-all font-mono text-num tnum lg:mt-0",
                      f.tone === "severe"
                        ? "text-sev-severe"
                        : f.tone === "info"
                          ? "text-info"
                          : "text-text-num",
                    )}
                    data-tabular-nums="true"
                  >
                    {f.value}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>

        {action !== undefined && (
          <div className="mt-6 flex flex-wrap gap-2 border-t border-border-1 pt-5">{action}</div>
        )}
      </div>
    </section>
  );
}

/**
 * Horizontal legend for the hand-rolled SVG charts.
 *
 * Charts previously each wrote their own legend markup, so the same series
 * could be described differently on two screens.
 */
export function ChartLegend({
  items,
  className,
}: {
  items: Array<{
    /** Token colour class, e.g. "text-info". */
    tone: string;
    /** Mark drawn in that colour: a dash, a dot, a band. */
    mark: string;
    label: string;
  }>;
  className?: string;
}): React.JSX.Element {
  return (
    <ul
      className={cn(
        "flex flex-wrap gap-x-4 gap-y-2 border-t border-border-1 pt-3 font-mono text-caption text-text-3",
        className,
      )}
    >
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-2">
          <span aria-hidden="true" className={i.tone}>
            {i.mark}
          </span>
          <span>{i.label}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * A row of headline figures as one grouped panel rather than N bordered
 * cards.
 *
 * Fewer frames, more rhythm: the page then has a small number of large
 * shapes instead of a uniform stack of same-weight rectangles. Figures use
 * the display size, which the locked scale provides but nothing else was
 * spending.
 */
export function StatStrip({
  items,
  testId,
}: {
  items: Array<{
    label: string;
    value: ReactNode;
    unit?: string;
    hint?: ReactNode;
    tone?: "default" | "severe" | "nominal" | "elevated" | "info";
    conceptKey?: string;
    settingKey?: string;
  }>;
  testId?: string;
}): React.JSX.Element {
  const TONES = {
    default: "text-text-num",
    severe: "text-sev-severe",
    nominal: "text-sev-nominal",
    elevated: "text-sev-elevated",
    info: "text-info",
  } as const;

  return (
    <dl
      data-testid={testId}
      className={cn(
        "relative grid grid-cols-1 gap-px overflow-hidden rounded-md",
        "border border-border-1 bg-border-1 shadow-card",
        "sm:grid-cols-2 xl:grid-cols-4",
        // A lit rule along the top edge: this is the instrument readout, not
        // another content panel.
        "before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:z-10",
        "before:h-px before:bg-accent before:opacity-60",
      )}
    >
      {items.map((item) => (
        <div
          key={item.label}
          className={cn(
            "min-w-0 px-5 py-4",
            "[background:linear-gradient(180deg,var(--surface-2),var(--surface-1)_60%)]",
          )}
        >
          <dt className="flex items-center gap-2">
            <span className="eyebrow min-w-0 flex-1 truncate">{item.label}</span>
            <TermHelp concept={item.conceptKey} setting={item.settingKey} label={item.label} />
          </dt>
          <dd className="mt-2 flex items-baseline gap-2">
            <span
              className={cn(
                "font-mono text-display font-semibold leading-none tracking-tight tnum",
                TONES[item.tone ?? "default"],
              )}
              data-tabular-nums="true"
            >
              {item.value}
            </span>
            {item.unit !== undefined && (
              <span className="font-mono text-caption text-text-3">{item.unit}</span>
            )}
          </dd>
          {item.hint !== undefined && (
            <p className="mt-2 text-caption leading-normal text-text-3">{item.hint}</p>
          )}
        </div>
      ))}
    </dl>
  );
}
