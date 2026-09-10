/**
 * Typography Tokens for LATENTIS (SIH26170)
 * 
 * Strict implementation of docs/UI_DESIGN_SYSTEM.md § 3.
 * 
 * Non-Negotiables:
 * 1. Numbers are typographically privileged. Monospaced numerals, aligned decimal points.
 * 2. `font-variant-numeric: tabular-nums lining-nums` mandatory wherever numbers are compared vertically.
 * 3. Fonts are vendored locally in public/fonts/, never fetched from a CDN (NFR-08 offline-first).
 *    Until the binaries land, the fallback tails below carry the design on every platform:
 *    the stacks name the closest grotesque / mono available on macOS, Windows and Linux
 *    rather than dropping to a generic `sans-serif` that would re-metric the whole UI.
 */

import type { FontFamilyToken, FontSizeToken, FontSizeConfig } from "./types";

/** Authoritative font families */
export const FONT_FAMILIES: Readonly<Record<FontFamilyToken, readonly string[]>> = Object.freeze({
  sans: [
    "Inter",
    "Inter var",
    "SF Pro Text",
    "system-ui",
    "-apple-system",
    "Segoe UI Variable Text",
    "Segoe UI",
    "Roboto",
    "Helvetica Neue",
    "sans-serif",
  ],
  mono: [
    "JetBrains Mono",
    "SF Mono",
    "ui-monospace",
    "Cascadia Mono",
    "Consolas",
    "Roboto Mono",
    "Liberation Mono",
    "monospace",
  ],
});

/** CSS font-family property strings */
export const FONT_FAMILY_STRINGS: Readonly<Record<FontFamilyToken, string>> = Object.freeze({
  sans: FONT_FAMILIES.sans.map((f) => (f.includes(" ") ? `"${f}"` : f)).join(", "),
  mono: FONT_FAMILIES.mono.map((f) => (f.includes(" ") ? `"${f}"` : f)).join(", "),
});

/**
 * Font size specifications with line-heights and semantic uses.
 */
export const FONT_SIZES: Readonly<Record<FontSizeToken, FontSizeConfig>> = Object.freeze({
  display: {
    size: "28px",
    lineHeight: "34px",
    use: "Verdict card headline",
  },
  h1: {
    size: "20px",
    lineHeight: "28px",
    use: "Surface title",
  },
  h2: {
    size: "16px",
    lineHeight: "24px",
    use: "Panel title",
  },
  body: {
    size: "14px",
    lineHeight: "20px",
    use: "Body",
  },
  num: {
    size: "15px",
    lineHeight: "20px",
    tabular: true,
    mono: true,
    use: "Table numerals",
  },
  "num-lg": {
    size: "22px",
    lineHeight: "26px",
    tabular: true,
    mono: true,
    use: "Verdict numerals",
  },
  caption: {
    size: "12px",
    lineHeight: "16px",
    use: "Units, provenance, captions",
  },
  formula: {
    size: "13px",
    lineHeight: "22px",
    mono: true,
    use: "The arithmetic panel",
  },
});

/** Numeric typography CSS rules enforcing tabular lining figures */
export const NUMERIC_FONT_VARIANT = "tabular-nums lining-nums";

/** Reusable Tailwind classes for numeric tabular cells */
export const NUMERIC_CLASSES = "font-mono tabular-nums lining-nums";

/**
 * Helper to get inline style object for numeric elements.
 */
export function getNumericStyle(): React.CSSProperties {
  return {
    fontFamily: FONT_FAMILY_STRINGS.mono,
    fontVariantNumeric: NUMERIC_FONT_VARIANT,
  };
}
