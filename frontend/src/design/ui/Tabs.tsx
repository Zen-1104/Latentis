import { useCallback, useRef } from "react";
import type { ReactNode } from "react";
import { cn } from "./cn";

export interface TabItem {
  id: string;
  label: ReactNode;
  /** Small trailing annotation, e.g. "worst". */
  note?: string;
  /** Per-tab test id; falls back to `${testIdPrefix}${id}`. */
  testId?: string;
}

interface TabsProps {
  items: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
  /** Accessible name for the tablist. */
  label: string;
  /** id of the panel the tabs control, for aria-controls. */
  panelId?: string;
  testIdPrefix?: string;
  className?: string;
}

/**
 * Underlined tab bar with the keyboard contract a tablist owes
 * (WAI-ARIA APG): arrows move, Home/End jump, and only the active tab is
 * tabbable, so Tab moves past the set rather than through every parameter.
 * The previous hand-rolled `role="tab"` buttons had none of that.
 */
export function Tabs({
  items,
  activeId,
  onChange,
  label,
  panelId,
  testIdPrefix = "tab-",
  className,
}: TabsProps): React.JSX.Element {
  const listRef = useRef<HTMLDivElement>(null);

  const focusAt = useCallback((index: number) => {
    const tabs = listRef.current?.querySelectorAll<HTMLButtonElement>("[role='tab']");
    if (tabs === undefined) return;
    const target = tabs[(index + tabs.length) % tabs.length];
    target?.focus();
    target?.click();
  }, []);

  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number): void => {
    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        event.preventDefault();
        focusAt(index + 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        event.preventDefault();
        focusAt(index - 1);
        break;
      case "Home":
        event.preventDefault();
        focusAt(0);
        break;
      case "End":
        event.preventDefault();
        focusAt(items.length - 1);
        break;
      default:
        break;
    }
  };

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={label}
      aria-orientation="horizontal"
      className={cn(
        "-mb-px flex items-stretch gap-1 overflow-x-auto border-b border-border-1",
        className,
      )}
    >
      {items.map((item, index) => {
        const selected = item.id === activeId;
        return (
          <button
            key={item.id}
            role="tab"
            type="button"
            id={`${testIdPrefix}${item.id}-tab`}
            aria-selected={selected}
            aria-controls={panelId}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.id)}
            onKeyDown={(e) => onKeyDown(e, index)}
            data-testid={item.testId ?? `${testIdPrefix}${item.id}`}
            className={cn(
              "relative -mb-px inline-flex h-control-md shrink-0 items-center gap-2 whitespace-nowrap",
              "border-b-2 px-3 font-mono text-body transition-colors duration-fast",
              "[@media(pointer:coarse)]:min-h-touch",
              selected
                ? "border-accent text-text-num"
                : "border-transparent text-text-2 hover:bg-hover hover:text-text-1",
            )}
          >
            {item.label}
            {item.note !== undefined && (
              <span className="text-caption text-sev-anomaly">{item.note}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Panel body paired with a `Tabs` set. */
export function TabPanel({
  id,
  labelledBy,
  children,
  className,
}: {
  id: string;
  labelledBy: string;
  children: ReactNode;
  className?: string;
}): React.JSX.Element {
  return (
    <div
      id={id}
      role="tabpanel"
      aria-labelledby={labelledBy}
      tabIndex={0}
      className={cn("outline-none", className)}
    >
      {children}
    </div>
  );
}
