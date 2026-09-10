import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "./cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "quiet";
export type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Leading icon or glyph; decorative, so it is hidden from the a11y tree. */
  icon?: ReactNode;
  /** Replaces the label with a busy affordance and blocks activation. */
  busy?: boolean;
  /** Stretches to the container — used for stacked mobile actions. */
  block?: boolean;
  children?: ReactNode;
}

const VARIANTS: Readonly<Record<ButtonVariant, string>> = {
  // The one filled control on a surface. Achromatic: a green "primary"
  // would read as a PASS verdict rather than as the main action.
  primary:
    "bg-accent text-accent-fg border border-transparent font-medium hover:opacity-90 active:opacity-100",
  secondary:
    "bg-surface-2 text-text-1 border border-border-2 hover:bg-surface-3 hover:border-text-3 active:bg-active",
  ghost:
    "bg-transparent text-text-2 border border-border-1 hover:bg-hover hover:text-text-1 hover:border-border-2",
  quiet:
    "bg-transparent text-text-2 border border-transparent hover:bg-hover hover:text-text-1",
};

const SIZES: Readonly<Record<ButtonSize, string>> = {
  sm: "h-control-sm px-2 text-caption gap-1",
  md: "h-control-md px-3 text-body gap-2",
  lg: "h-control-lg px-4 text-body gap-2",
};

/**
 * The single button primitive. Before this existed the same
 * `px-3 py-1.5 border border-border-2 rounded-sm …` string was pasted into
 * a dozen files — and `py-1.5` is not on the locked spacing scale, so every
 * one of those controls was rendering at text height with no padding at all.
 * Height is tokenised here instead (`--control-h-*`) so every control in
 * the app shares one baseline.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    size = "md",
    icon,
    busy = false,
    block = false,
    className,
    disabled,
    children,
    type = "button",
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled === true || busy}
      aria-busy={busy || undefined}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-sm",
        "transition-colors duration-fast",
        "disabled:cursor-not-allowed disabled:opacity-50",
        // Coarse pointers get a compliant target without inflating the
        // desktop rhythm (WCAG 2.5.5).
        "[@media(pointer:coarse)]:min-h-touch",
        SIZES[size],
        VARIANTS[variant],
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {busy ? (
        <span aria-hidden="true" className="inline-block h-2 w-2 rounded-full bg-current opacity-70" />
      ) : (
        icon !== undefined && (
          <span aria-hidden="true" className="inline-flex shrink-0 items-center">
            {icon}
          </span>
        )
      )}
      {children !== undefined && <span className="truncate">{children}</span>}
    </button>
  );
});

interface IconButtonProps extends Omit<ButtonProps, "children" | "icon" | "block"> {
  /** Required: an icon-only control has no visible label. */
  label: string;
  icon: ReactNode;
}

/** Icon-only control. The accessible name is mandatory, not optional. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, variant = "quiet", size = "md", className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-sm",
        "transition-colors duration-fast disabled:cursor-not-allowed disabled:opacity-50",
        "[@media(pointer:coarse)]:min-h-touch [@media(pointer:coarse)]:min-w-touch",
        size === "sm" ? "h-control-sm w-control-sm" : size === "lg" ? "h-control-lg w-control-lg" : "h-control-md w-control-md",
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      <span aria-hidden="true" className="inline-flex items-center justify-center">
        {icon}
      </span>
    </button>
  );
});
