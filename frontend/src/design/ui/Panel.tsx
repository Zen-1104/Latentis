import type { ReactNode } from "react";
import { cn } from "./cn";

interface PanelProps {
  children: ReactNode;
  className?: string;
  /** Emphasised border for a panel carrying a degraded or failing state. */
  tone?: "default" | "severe" | "weak" | "void";
  testId?: string;
  as?: "div" | "section" | "aside";
  ariaLabel?: string;
}

const TONES: Readonly<Record<NonNullable<PanelProps["tone"]>, string>> = {
  default: "border-border-1",
  severe: "border-sev-severe",
  weak: "border-evidence-weak",
  void: "border-guard-void",
};

/**
 * The app's one container. Panels are bordered, never shadowed
 * (UI_DESIGN_SYSTEM § 4) — elevation is reserved for the drawer and
 * popovers, which genuinely float.
 */
export function Panel({
  children,
  className,
  tone = "default",
  testId,
  as = "div",
  ariaLabel,
}: PanelProps): React.JSX.Element {
  const Tag = as;
  return (
    <Tag
      data-testid={testId}
      aria-label={ariaLabel}
      className={cn("rounded-md border bg-surface-1", TONES[tone], className)}
    >
      {children}
    </Tag>
  );
}

interface PanelHeaderProps {
  title: ReactNode;
  /** Small monospaced index, e.g. an evidence-chain step or surface code. */
  index?: string;
  /** Right-aligned metadata or controls. */
  actions?: ReactNode;
  /** Sub-line under the title. */
  hint?: ReactNode;
  className?: string;
  /** Heading level for the title — sections nest, so this must be explicit. */
  level?: 2 | 3;
  id?: string;
}

/** Panel title bar: index, title, optional hint, right-aligned actions. */
export function PanelHeader({
  title,
  index,
  actions,
  hint,
  className,
  level = 2,
  id,
}: PanelHeaderProps): React.JSX.Element {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <header
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border-1 px-4 py-3",
        className,
      )}
    >
      {index !== undefined && (
        <span
          aria-hidden="true"
          className="inline-flex h-chip min-w-control-md items-center justify-center rounded-sm border border-border-1 bg-surface-2 px-1 font-mono text-caption text-text-3"
        >
          {index}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <Heading id={id} className="truncate text-h2 font-semibold text-text-1">
          {title}
        </Heading>
        {hint !== undefined && <div className="mt-1 text-caption text-text-3">{hint}</div>}
      </div>
      {actions !== undefined && (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      )}
    </header>
  );
}

/** Panel content region with the standard inset and vertical rhythm. */
export function PanelBody({
  children,
  className,
  flush = false,
}: {
  children: ReactNode;
  className?: string;
  /** Drop the inset — for tables and maps that supply their own edges. */
  flush?: boolean;
}): React.JSX.Element {
  return <div className={cn(!flush && "space-y-4 p-4", className)}>{children}</div>;
}

/**
 * Uppercase monospaced field label. Used for every key in the app's
 * key/value displays so metadata reads consistently everywhere.
 */
export function FieldLabel({
  children,
  className,
  as = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "span" | "dt";
}): React.JSX.Element {
  const Tag = as;
  return <Tag className={cn("eyebrow", className)}>{children}</Tag>;
}
