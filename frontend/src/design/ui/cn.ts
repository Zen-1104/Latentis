import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * Font sizes from the locked scale (`tailwind.config.ts` -> `theme.fontSize`).
 *
 * These have to be declared to tailwind-merge explicitly. Its built-in
 * knowledge of `text-*` covers Tailwind's default `text-xs .. text-9xl`, and
 * anything else under `text-` it classifies as a *colour*. Because this
 * project replaces the whole scale with named steps, every one of them was
 * being read as a colour — so in a call like
 *
 *   cn("text-display font-semibold", "text-text-1")
 *
 * twMerge saw two colours, applied last-wins, and silently dropped the size.
 * The class list reaching the DOM carried no font-size at all and the element
 * inherited 14px, which is why headings and figures on every surface rendered
 * at body size regardless of the token they asked for.
 */
const FONT_SIZES = [
  "hero",
  "display",
  "h1",
  "h2",
  "body",
  "num",
  "num-lg",
  "caption",
  "formula",
] as const;

/**
 * Colour tokens written at the top level of `theme.colors`, i.e. the ones
 * whose utility is `text-<name>`.
 *
 * `num` is deliberately absent: the *font size* is `text-num`, while the
 * numeric *colour* is `text-text-num` (nested under `text`), so listing it
 * here would put the two groups back in conflict.
 */
const COLORS = [
  "sev-nominal",
  "sev-elevated",
  "sev-anomaly",
  "sev-severe",
  "sev-critical",
  "evidence-weak",
  "guard-void",
  "synthetic",
  "baseline",
  "bound-fill",
  "accent",
  "accent-fg",
  "accent-soft",
  "info",
  "info-soft",
  "focus",
  "hover",
  "active",
  "overlay",
  "current",
  "transparent",
] as const;

/** Colours nested under `text`, i.e. `text-text-1` .. `text-text-num`. */
const TEXT_COLORS = ["1", "2", "3", "num"] as const;

/**
 * Named layout dimensions from `tailwind.config.ts` -> `theme.extend`.
 *
 * They have to be declared for the same reason the font sizes do: twMerge
 * only recognises Tailwind's own scale values, so a custom key does not
 * conflict with a built-in one and both classes survive — leaving the winner
 * to stylesheet order rather than to author order.
 */
const SIZES = {
  w: ["label", "sidebar", "rail", "cell", "chip", "control-sm", "control-md", "control-lg"],
  h: ["cell", "chip", "row", "control-sm", "control-md", "control-lg", "header", "bar", "bar-thin", "hair"],
  minW: ["label", "control-md", "touch"],
  minH: ["control-sm", "control-md", "control-lg", "touch"],
  maxW: ["prose", "measure", "content"],
  maxH: ["list", "panel"],
} as const;

const merge = extendTailwindMerge({
  extend: {
    classGroups: {
      w: [{ w: [...SIZES.w] }],
      h: [{ h: [...SIZES.h] }],
      "min-w": [{ "min-w": [...SIZES.minW] }],
      "min-h": [{ "min-h": [...SIZES.minH] }],
      "max-w": [{ "max-w": [...SIZES.maxW] }],
      "max-h": [{ "max-h": [...SIZES.maxH] }],
    },
  },
  override: {
    classGroups: {
      "font-size": [{ text: [...FONT_SIZES] }],
      "text-color": [{ text: [...COLORS, { text: [...TEXT_COLORS] }] }],
    },
  },
});

/**
 * Conditional class composition with last-wins conflict resolution.
 *
 * Components in this layer expose a `className` prop so callers can adjust
 * layout without forking the component; the merge makes that override
 * predictable instead of depending on stylesheet order.
 */
export function cn(...inputs: ClassValue[]): string {
  return merge(clsx(inputs));
}
