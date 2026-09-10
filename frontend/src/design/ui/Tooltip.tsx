import { useId, useState } from "react";
import type { ReactNode } from "react";
import { cn } from "./cn";

interface TooltipProps {
  /** Tooltip body. Kept short — anything longer belongs in the panel. */
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom";
  align?: "start" | "center" | "end";
  className?: string;
}

/**
 * Hover *and* focus tooltip, wired with `aria-describedby` so the text
 * reaches assistive tech instead of only the pointer. The app leaned on
 * `title` attributes, which never appear on keyboard focus and are
 * unreadable on touch.
 *
 * Not a substitute for a label: every control it wraps keeps its own
 * accessible name.
 */
export function Tooltip({
  content,
  children,
  side = "top",
  align = "center",
  className,
}: TooltipProps): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const id = useId();

  return (
    <span
      className={cn("relative inline-flex", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape") setOpen(false);
      }}
    >
      <span aria-describedby={open ? id : undefined} className="inline-flex">
        {children}
      </span>
      <span
        role="tooltip"
        id={id}
        hidden={!open}
        className={cn(
          "pointer-events-none absolute z-popover w-max max-w-prose animate-fade-in",
          "rounded-md border border-border-2 bg-surface-3 px-3 py-2 shadow-popover",
          "text-caption font-normal leading-normal text-text-1",
          side === "top" ? "bottom-full mb-2" : "top-full mt-2",
          align === "center" && "left-1/2 -translate-x-1/2",
          align === "start" && "left-0",
          align === "end" && "right-0",
        )}
      >
        {content}
      </span>
    </span>
  );
}

/**
 * A small "?" affordance that carries an explanation. Used beside technical
 * labels where the term itself is the thing needing definition.
 */
export function InfoHint({ children, label }: { children: ReactNode; label: string }): React.JSX.Element {
  return (
    <Tooltip content={children}>
      <button
        type="button"
        aria-label={label}
        className={cn(
          "inline-flex h-chip w-chip items-center justify-center rounded-full",
          "border border-border-1 bg-surface-2 font-mono text-caption text-text-3",
          "transition-colors duration-fast hover:border-border-2 hover:text-text-1",
        )}
      >
        <span aria-hidden="true">?</span>
      </button>
    </Tooltip>
  );
}
