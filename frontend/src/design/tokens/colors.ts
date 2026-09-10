/**
 * Color Tokens for LATENTIS (SIH26170)
 * 
 * Strict implementation of docs/UI_DESIGN_SYSTEM.md § 2.
 * 
 * Invariants & Charter Rules:
 * 1. Colour carries severity only, never decoration.
 * 2. --sev-critical is violet (#8E2B7A / #7B2169), NOT red. An absolute limit failure
 *    is categorically distinct from a lot-relative anomaly.
 * 3. --evidence-weak is blue (#5B7C9E / #456482), NOT red. Weak evidence indicates
 *    lack of confidence, not that a part is bad.
 * 4. Contrast ratio >= 4.5:1 is maintained across both dark (primary) and light themes (TEST-A11Y-001).
 */

import type {
  ColorToken,
  SurfaceToken,
  BorderToken,
  TextToken,
  SeverityToken,
  EvidenceToken,
  GuardToken,
  SyntheticToken,
  ChartColorToken,
  InteractionToken,
  Theme,
} from "./types";

/**
 * Dark theme color values (primary theme).
 * Restrained, dense, high-contrast, low-emission.
 */
export const DARK_COLORS: Readonly<Record<ColorToken, string>> = Object.freeze({
  // Surfaces
  "surface-0": "#0B0F14",
  "surface-1": "#11171F",
  "surface-2": "#18202B",
  "surface-3": "#202A38",

  // Borders
  "border-1": "#263241",
  "border-2": "#33445A",

  // Typography text
  "text-1": "#E8EEF6",
  "text-2": "#A9B7C8",
  "text-3": "#6F8095",
  "text-num": "#F2F7FD",

  // Semantic Severities
  "sev-nominal": "#3FA46A",
  "sev-elevated": "#C9A227",
  "sev-anomaly": "#D97A25",
  "sev-severe": "#C8442E",
  "sev-critical": "#8E2B7A", // Violet hue: distinct from lot-relative anomaly

  // Evidence & Guard
  "evidence-weak": "#5B7C9E", // Blue family: data quality / reduced power / censored
  "guard-void": "#B0432A",
  "synthetic": "#7A5CC4", // Dedicated synthetic badge color

  // Chart tokens
  "baseline": "#7C8899",
  "bound-fill": "rgba(63, 164, 106, 0.14)",

  // Interaction chrome — achromatic by charter (see InteractionToken).
  "accent": "#DCE6F4",
  "accent-fg": "#0B0F14",
  "accent-soft": "rgba(220, 230, 244, 0.10)",
  "hover": "rgba(220, 230, 244, 0.05)",
  "active": "rgba(220, 230, 244, 0.10)",
  "focus-ring": "#8FA6C2",
  "overlay": "rgba(5, 8, 11, 0.66)",
});

/**
 * Light theme color values (projector / report export).
 * Audited for >= 4.5:1 contrast against surface-0/1.
 */
export const LIGHT_COLORS: Readonly<Record<ColorToken, string>> = Object.freeze({
  // Surfaces
  "surface-0": "#F6F8FB",
  "surface-1": "#FFFFFF",
  "surface-2": "#EDF2F7",
  "surface-3": "#E2E8F0",

  // Borders
  "border-1": "#D2DCE6",
  "border-2": "#B0C0D2",

  // Typography text
  "text-1": "#0F172A",
  "text-2": "#334155",
  "text-3": "#64748B",
  "text-num": "#090D16",

  // Semantic Severities
  "sev-nominal": "#2E7D4F",
  "sev-elevated": "#A17D16",
  "sev-anomaly": "#C0641A",
  "sev-severe": "#B33622",
  "sev-critical": "#7B2169",

  // Evidence & Guard
  "evidence-weak": "#456482",
  "guard-void": "#9B341D",
  "synthetic": "#694CB5",

  // Chart tokens
  "baseline": "#64748B",
  "bound-fill": "rgba(46, 125, 79, 0.14)",

  // Interaction chrome — achromatic by charter (see InteractionToken).
  "accent": "#16233A",
  "accent-fg": "#FFFFFF",
  "accent-soft": "rgba(22, 35, 58, 0.07)",
  "hover": "rgba(15, 23, 42, 0.04)",
  "active": "rgba(15, 23, 42, 0.08)",
  "focus-ring": "#3B5878",
  "overlay": "rgba(15, 23, 42, 0.40)",
});

/** CSS variable names for each token */
export const COLOR_CSS_VARS: Readonly<Record<ColorToken, string>> = Object.freeze({
  "surface-0": "--surface-0",
  "surface-1": "--surface-1",
  "surface-2": "--surface-2",
  "surface-3": "--surface-3",
  "border-1": "--border-1",
  "border-2": "--border-2",
  "text-1": "--text-1",
  "text-2": "--text-2",
  "text-3": "--text-3",
  "text-num": "--text-num",
  "sev-nominal": "--sev-nominal",
  "sev-elevated": "--sev-elevated",
  "sev-anomaly": "--sev-anomaly",
  "sev-severe": "--sev-severe",
  "sev-critical": "--sev-critical",
  "evidence-weak": "--evidence-weak",
  "guard-void": "--guard-void",
  "synthetic": "--synthetic",
  "baseline": "--baseline",
  "bound-fill": "--bound-fill",
  "accent": "--accent",
  "accent-fg": "--accent-fg",
  "accent-soft": "--accent-soft",
  "hover": "--hover",
  "active": "--active",
  "focus-ring": "--focus-ring",
  "overlay": "--overlay",
});

export const SURFACE_TOKENS: readonly SurfaceToken[] = [
  "surface-0",
  "surface-1",
  "surface-2",
  "surface-3",
];

export const BORDER_TOKENS: readonly BorderToken[] = [
  "border-1",
  "border-2",
];

export const TEXT_TOKENS: readonly TextToken[] = [
  "text-1",
  "text-2",
  "text-3",
  "text-num",
];

export const SEVERITY_TOKENS: readonly SeverityToken[] = [
  "sev-nominal",
  "sev-elevated",
  "sev-anomaly",
  "sev-severe",
  "sev-critical",
];

export const EVIDENCE_TOKENS: readonly EvidenceToken[] = ["evidence-weak"];
export const GUARD_TOKENS: readonly GuardToken[] = ["guard-void"];
export const SYNTHETIC_TOKENS: readonly SyntheticToken[] = ["synthetic"];
export const CHART_COLOR_TOKENS: readonly ChartColorToken[] = ["baseline", "bound-fill"];

export const INTERACTION_TOKENS: readonly InteractionToken[] = [
  "accent",
  "accent-fg",
  "accent-soft",
  "hover",
  "active",
  "focus-ring",
  "overlay",
];

/**
 * Returns the CSS variable expression for a token (e.g., `var(--surface-0)`).
 */
export function getColorCssVar(token: ColorToken): string {
  const cssVar = COLOR_CSS_VARS[token];
  const fallback = DARK_COLORS[token];
  return `var(${cssVar}, ${fallback})`;
}

/**
 * Returns the literal hex or rgba string for a token under a specified theme.
 */
export function getColorValue(token: ColorToken, theme: Theme = "dark"): string {
  const palette = theme === "dark" ? DARK_COLORS : LIGHT_COLORS;
  return palette[token];
}

/**
 * Parses a hex color or rgb/rgba string into RGBA components [0..255].
 */
export function parseColor(color: string): { r: number; g: number; b: number; a: number } {
  const trimmed = color.trim();

  // Hex format: #RGB, #RGBA, #RRGGBB, #RRGGBBAA
  if (trimmed.startsWith("#")) {
    let hex = trimmed.slice(1);
    if (hex.length === 3 || hex.length === 4) {
      hex = hex
        .split("")
        .map((c) => c + c)
        .join("");
    }
    const num = parseInt(hex, 16);
    if (hex.length === 6) {
      return {
        r: (num >> 16) & 255,
        g: (num >> 8) & 255,
        b: num & 255,
        a: 1.0,
      };
    }
    if (hex.length === 8) {
      return {
        r: (num >> 24) & 255,
        g: (num >> 16) & 255,
        b: (num >> 8) & 255,
        a: (num & 255) / 255,
      };
    }
  }

  // RGBA format: rgba(r, g, b, a) or rgb(r, g, b)
  const match = trimmed.match(/^rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)$/i);
  if (match && match[1] && match[2] && match[3]) {
    return {
      r: parseInt(match[1], 10),
      g: parseInt(match[2], 10),
      b: parseInt(match[3], 10),
      a: match[4] !== undefined ? parseFloat(match[4]) : 1.0,
    };
  }

  throw new Error(`Invalid color format: ${color}`);
}

/**
 * Calculates WCAG 2.1 relative luminance for an sRGB color.
 */
export function getRelativeLuminance(color: string): number {
  const { r, g, b } = parseColor(color);
  const transform = (channel: number): number => {
    const v = channel / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  const R = transform(r);
  const G = transform(g);
  const B = transform(b);
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

/**
 * Computes the contrast ratio between foreground and background colors.
 * Formula: (L1 + 0.05) / (L2 + 0.05), where L1 is lighter and L2 is darker.
 */
export function getContrastRatio(fg: string, bg: string): number {
  const lum1 = getRelativeLuminance(fg);
  const lum2 = getRelativeLuminance(bg);
  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);
  return (lighter + 0.05) / (darker + 0.05);
}
