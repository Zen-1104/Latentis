import { useCallback, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { cn } from "./cn";

interface TooltipProps {
  /** Tooltip body. Kept short — anything longer belongs in the panel. */
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom" | "right";
  align?: "start" | "center" | "end";
  /**
   * Position the bubble against the viewport instead of the trigger's
   * containing block.
   *
   * Needed where an ancestor clips: a scrollable container computes
   * `overflow-x` to `auto` as well, so an absolutely-positioned bubble that
   * overhangs it is cut off. Opt in only where that applies — the default
   * path stays pure CSS.
   */
  float?: boolean;
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
  float = false,
  className,
}: TooltipProps): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const id = useId();

  const show = useCallback(() => {
    if (float) {
      const el = triggerRef.current;
      if (el !== null) {
        const r = el.getBoundingClientRect();
        setPos(
          side === "right"
            ? { left: r.right + 8, top: r.top + r.height / 2 }
            : { left: r.left + r.width / 2, top: side === "top" ? r.top - 8 : r.bottom + 8 },
        );
      }
    }
    setOpen(true);
  }, [float, side]);

  return (
    <span
      className={cn("relative inline-flex", className)}
      onMouseEnter={show}
      onMouseLeave={() => setOpen(false)}
      onFocus={show}
      onBlur={() => setOpen(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape") setOpen(false);
      }}
    >
      {/* `w-full` on the outer wrapper is inherited here too, so a trigger
          that wants to fill its host (the collapsed nav rail) can. */}
      <span
        ref={triggerRef}
        aria-describedby={open ? id : undefined}
        className="inline-flex w-full justify-center"
      >
        {children}
      </span>
      <span
        role="tooltip"
        id={id}
        hidden={!open}
        style={
          float && pos !== null
            ? {
                position: "fixed",
                left: pos.left,
                top: pos.top,
                transform:
                  side === "right"
                    ? "translateY(-50%)"
                    : side === "top"
                      ? "translate(-50%, -100%)"
                      : "translateX(-50%)",
              }
            : undefined
        }
        className={cn(
          "pointer-events-none z-popover w-max max-w-prose animate-fade-in",
          "rounded-md border border-border-2 bg-surface-3 px-3 py-2 shadow-popover",
          "text-caption font-normal leading-normal text-text-1",
          float ? "fixed" : "absolute",
          !float && (side === "top" ? "bottom-full mb-2" : "top-full mt-2"),
          !float && align === "center" && "left-1/2 -translate-x-1/2",
          !float && align === "start" && "left-0",
          !float && align === "end" && "right-0",
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
