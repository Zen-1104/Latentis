import type { ReactNode } from "react";
import { cn } from "./cn";

interface PageHeaderProps {
  /** Surface code and route, e.g. "S3 · #/components/C-L-2026-002-0049". */
  eyebrow: string;
  title: ReactNode;
  /** One or two sentences on what this surface answers. */
  description?: ReactNode;
  /** Primary/secondary actions for the surface. */
  actions?: ReactNode;
  /** Chips rendered beside the title (verdicts, identity). */
  badges?: ReactNode;
  /** Identity metadata below the title (lot, socket, zone, tester). */
  meta?: ReactNode;
  /** Renders the title in mono — used where the title is an entity id. */
  monoTitle?: boolean;
  className?: string;
}

/**
 * One header for all eight surfaces. Every view previously hand-rolled the
 * same eyebrow/h1/paragraph stack with slightly different spacing, which is
 * what made the surfaces feel like different applications.
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  badges,
  meta,
  monoTitle = false,
  className,
}: PageHeaderProps): React.JSX.Element {
  return (
    <header className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0 space-y-2">
          <p className="eyebrow break-all">{eyebrow}</p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h1
              className={cn(
                "text-h1 font-semibold",
                monoTitle ? "break-all font-mono text-text-num" : "text-text-1",
              )}
            >
              {title}
            </h1>
            {badges}
          </div>
        </div>
        {actions !== undefined && (
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        )}
      </div>
      {description !== undefined && (
        <p className="max-w-prose text-body text-text-2">{description}</p>
      )}
      {meta}
    </header>
  );
}

/**
 * Inline key/value metadata row — the `lot X · type Y · socket Z` strip
 * under an entity title. A definition list, because that is what it is.
 */
export function MetaList({
  items,
  className,
  testId,
}: {
  items: Array<{ label: string; value: ReactNode; key?: string }>;
  className?: string;
  testId?: string;
}): React.JSX.Element {
  return (
    <dl
      data-testid={testId}
      className={cn("flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-caption", className)}
    >
      {items.map((item) => (
        <div key={item.key ?? item.label} className="flex items-center gap-2">
          <dt className="text-text-3">{item.label}</dt>
          <dd className="text-text-num">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
