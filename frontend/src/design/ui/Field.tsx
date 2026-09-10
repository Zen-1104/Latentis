import { forwardRef, useId } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { cn } from "./cn";

const CONTROL_BASE = cn(
  "w-full rounded-sm border bg-surface-2 px-3 text-body text-text-1",
  "border-border-1 placeholder:text-text-3",
  "transition-colors duration-fast",
  "hover:border-border-2",
  "disabled:cursor-not-allowed disabled:opacity-50",
  "aria-[invalid=true]:border-sev-severe",
);

interface FieldShellProps {
  label: string;
  /** Helper text under the control. */
  hint?: ReactNode;
  /** Validation message. Replaces the hint and marks the control invalid. */
  error?: string | null;
  /** Rendered when the field is not strictly required. */
  optional?: boolean;
  /** Test id for the validation message, where a contract asserts on it. */
  errorTestId?: string;
  children: (ids: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
  className?: string;
}

/**
 * Label + control + hint/error, wired with real `htmlFor` /
 * `aria-describedby` / `aria-invalid`. Fields across the app previously
 * wrapped inputs in a bare `<label>` with a styled `<span>`, so validation
 * messages were never announced and never associated with the input.
 */
export function Field({
  label,
  hint,
  error,
  optional = false,
  errorTestId,
  children,
  className,
}: FieldShellProps): React.JSX.Element {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const invalid = error !== null && error !== undefined && error !== "";
  const describedBy = invalid ? errorId : hint !== undefined ? hintId : undefined;

  return (
    <div className={cn("min-w-0 space-y-1", className)}>
      <label htmlFor={id} className="flex items-center gap-2">
        <span className="eyebrow">{label}</span>
        {optional && <span className="text-caption text-text-3">optional</span>}
      </label>
      {children({ id, describedBy, invalid })}
      {invalid ? (
        <p
          id={errorId}
          role="alert"
          data-testid={errorTestId}
          className="flex items-start gap-1 text-caption text-sev-severe"
        >
          <span aria-hidden="true">✗</span>
          <span>{error}</span>
        </p>
      ) : (
        hint !== undefined && (
          <p id={hintId} className="text-caption text-text-3">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

/** Text input matching the shared control height. */
export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function TextInput({ className, ...rest }, ref) {
    return (
      <input
        ref={ref}
        className={cn(CONTROL_BASE, "h-control-md", "[@media(pointer:coarse)]:min-h-touch", className)}
        {...rest}
      />
    );
  },
);

/** Select matching the shared control height, with a token-drawn chevron. */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select
        ref={ref}
        className={cn(
          CONTROL_BASE,
          "token-select h-control-md cursor-pointer pr-8",
          "[@media(pointer:coarse)]:min-h-touch",
          className,
        )}
        {...rest}
      >
        {children}
      </select>
    );
  },
);

/**
 * Search / filter input with a leading glyph and a clear affordance.
 * Component directories run to hundreds of parts; scanning them by eye was
 * the only option before this existed.
 */
export function SearchInput({
  value,
  onChange,
  label,
  placeholder,
  testId,
  className,
  resultCount,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder?: string;
  testId?: string;
  className?: string;
  /** Announced politely so filtering feedback reaches screen readers. */
  resultCount?: number;
}): React.JSX.Element {
  const id = useId();
  return (
    <div className={cn("min-w-0", className)}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className="relative">
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 font-mono text-caption text-text-3"
        >
          ⌕
        </span>
        <input
          id={id}
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          data-testid={testId}
          className={cn(
            CONTROL_BASE,
            "h-control-md pl-8 pr-8 font-mono",
            "[@media(pointer:coarse)]:min-h-touch",
            "[&::-webkit-search-cancel-button]:hidden",
          )}
        />
        {value !== "" && (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label="Clear filter"
            className="absolute right-1 top-1/2 inline-flex h-control-sm w-control-sm -translate-y-1/2 items-center justify-center rounded-sm font-mono text-caption text-text-3 transition-colors duration-fast hover:bg-hover hover:text-text-1"
          >
            <span aria-hidden="true">✕</span>
          </button>
        )}
      </div>
      {resultCount !== undefined && (
        <p aria-live="polite" className="sr-only">
          {resultCount} results
        </p>
      )}
    </div>
  );
}
