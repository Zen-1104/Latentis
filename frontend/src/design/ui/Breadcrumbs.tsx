import { navigate, type Route } from "../../router";
import { cn } from "./cn";

export interface Crumb {
  label: string;
  /** Omit on the current page — the last crumb is not a link. */
  to?: Route;
}

/**
 * Contextual trail (Phase 22).
 *
 * The app is a drill-down — programme, then lot, then component, then its
 * forecast — but the hash router carries no visible hierarchy, so a reader
 * who deep-linked into a component had no way to see where they were or to
 * step back up. Rendered as a real `<nav>` with an ordered list so the
 * structure is available to assistive tech, and the current page is marked
 * `aria-current`.
 */
export function Breadcrumbs({
  items,
  className,
}: {
  items: Crumb[];
  className?: string;
}): React.JSX.Element | null {
  if (items.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className={cn("min-w-0", className)}>
      <ol className="flex flex-wrap items-center gap-x-1 gap-y-1 font-mono text-caption">
        {items.map((crumb, i) => {
          const isLast = i === items.length - 1;
          return (
            <li key={`${crumb.label}-${i}`} className="flex min-w-0 items-center gap-1">
              {i > 0 && (
                <span aria-hidden="true" className="px-1 text-text-3">
                  /
                </span>
              )}
              {isLast || crumb.to === undefined ? (
                <span
                  aria-current={isLast ? "page" : undefined}
                  className="max-w-full truncate text-text-2"
                >
                  {crumb.label}
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    if (crumb.to !== undefined) navigate(crumb.to);
                  }}
                  className={cn(
                    "inline-flex max-w-full items-center truncate rounded-sm text-text-3 underline",
                    "decoration-border-2 decoration-dotted underline-offset-4",
                    "transition-colors duration-fast hover:text-text-1 hover:decoration-text-num",
                    "[@media(pointer:coarse)]:min-h-touch",
                  )}
                >
                  {crumb.label}
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
