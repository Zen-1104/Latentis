import { useCallback, useRef } from "react";
import type { ReactNode } from "react";
import { cn } from "./cn";

export interface SegmentItem<T extends string> {
  value: T;
  label: ReactNode;
  /** Optional hint surfaced as the control's title. */
  hint?: string;
  testId?: string;
}

interface SegmentedProps<T extends string> {
  items: Array<SegmentItem<T>>;
  value: T;
  onChange: (value: T) => void;
  /** Accessible name for the group. */
  label: string;
  size?: "sm" | "md";
  className?: string;
}

/**
 * Single-choice segmented control (disposition action, report format,
 * density). A real radiogroup: arrows move the selection, only the checked
 * option is tabbable. The chip rows this replaces exposed
 * `role="radio"` without any of the keyboard behaviour that implies.
 */
export function Segmented<T extends string>({
  items,
  value,
  onChange,
  label,
  size = "md",
  className,
}: SegmentedProps<T>): React.JSX.Element {
  const groupRef = useRef<HTMLDivElement>(null);

  const moveTo = useCallback((index: number) => {
    const radios = groupRef.current?.querySelectorAll<HTMLButtonElement>("[role='radio']");
    if (radios === undefined) return;
    const target = radios[(index + radios.length) % radios.length];
    target?.focus();
    target?.click();
  }, []);

  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number): void => {
    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        event.preventDefault();
        moveTo(index + 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        event.preventDefault();
        moveTo(index - 1);
        break;
      default:
        break;
    }
  };

  return (
    <div
      ref={groupRef}
      role="radiogroup"
      aria-label={label}
      className={cn(
        "inline-flex max-w-full flex-wrap items-center gap-1 rounded-md border border-border-1 bg-surface-2 p-1",
        className,
      )}
    >
      {items.map((item, index) => {
        const checked = item.value === value;
        return (
          <button
            key={item.value}
            role="radio"
            type="button"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            title={item.hint}
            onClick={() => onChange(item.value)}
            onKeyDown={(e) => onKeyDown(e, index)}
            data-testid={item.testId}
            className={cn(
              "inline-flex shrink-0 items-center justify-center rounded-sm font-mono transition-colors duration-fast",
              "[@media(pointer:coarse)]:min-h-touch",
              size === "sm" ? "h-control-sm px-2 text-caption" : "h-control-md px-3 text-body",
              checked
                ? "bg-accent text-accent-fg font-medium"
                : "text-text-2 hover:bg-hover hover:text-text-1",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Multi-select chip row (filters, shape-group pickers). Distinct from
 * `Segmented` because the selection is not exclusive and the control is a
 * set of toggle buttons, not a radiogroup.
 */
export function ToggleChips<T extends string>({
  items,
  selected,
  onToggle,
  label,
  className,
}: {
  items: Array<SegmentItem<T>>;
  selected: readonly T[];
  onToggle: (value: T) => void;
  label: string;
  className?: string;
}): React.JSX.Element {
  return (
    <div role="group" aria-label={label} className={cn("flex flex-wrap items-center gap-1", className)}>
      {items.map((item) => {
        const on = selected.includes(item.value);
        return (
          <button
            key={item.value}
            type="button"
            aria-pressed={on}
            title={item.hint}
            onClick={() => onToggle(item.value)}
            data-testid={item.testId}
            className={cn(
              "inline-flex h-control-sm items-center rounded-sm border px-2 font-mono text-caption",
              "transition-colors duration-fast [@media(pointer:coarse)]:min-h-touch",
              on
                ? "border-accent bg-accent-soft text-text-num"
                : "border-border-1 text-text-2 hover:border-border-2 hover:bg-hover hover:text-text-1",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
