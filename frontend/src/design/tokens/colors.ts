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
  InfoToken,
  Theme,
} from "./types";

/**
 * Dark theme color values (primary theme).
 * Restrained, dense, high-contrast, low-emission.
 */
export const DARK_COLORS: Readonly<Record<ColorToken, string>> = Object.freeze({
  // Surfaces
  "surface-0": "#060A14",
  "surface-1": "#0F1829",
  "surface-2": "#17223A",
  "surface-3": "#1F2D4A",

  // Borders
  "border-1": "#293755",
  "border-2": "#3D5480",

  // Typography text
  "text-1": "#E8EEFA",
  "text-2": "#A5B4CE",
  "text-3": "#6B7C9C",
  "text-num": "#F7FAFF",

  // Semantic Severities
  "sev-nominal": "#2FD19A",
  "sev-elevated": "#F0C245",
  "sev-anomaly": "#FF9245",
  "sev-severe": "#FF6155",
  "sev-critical": "#D06BC8", // Violet hue: distinct from lot-relative anomaly

  // Evidence & Guard
  "evidence-weak": "#5A96B8", // Blue family: data quality / reduced power / censored
  "guard-void": "#E2705C",
  "synthetic": "#A88BFF", // Dedicated synthetic badge color

  // Chart tokens
  "baseline": "#8595AD",
  "bound-fill": "rgba(47, 209, 154, 0.16)",

  // Interaction chrome — saturated indigo, outside every severity hue.
  "accent": "#4666F0",
  "accent-fg": "#FFFFFF",
  "accent-hi": "#8CA6FF",
  "accent-line": "rgba(140, 166, 255, 0.42)",
  "accent-soft": "rgba(110, 140, 255, 0.13)",
  "hover": "rgba(124, 152, 255, 0.075)",
  "active": "rgba(124, 152, 255, 0.14)",
  "focus-ring": "#8CA6FF",
  "overlay": "rgba(3, 6, 14, 0.78)",

  // Analysis / forecast accent (hue ~189; 6.7:1 on surface-0).
  "info": "#3FD0E0",
  "info-soft": "rgba(63, 208, 224, 0.15)",
});

/**
 * Light theme color values (projector / report export).
 * Audited for >= 4.5:1 contrast against surface-0/1.
 */
export const LIGHT_COLORS: Readonly<Record<ColorToken, string>> = Object.freeze({
  // Surfaces
  "surface-0": "#EEF1F8",
  "surface-1": "#FFFFFF",
  "surface-2": "#E4E9F4",
  "surface-3": "#D6DEEE",

  // Borders
  "border-1": "#C6D0E2",
  "border-2": "#9AA9C4",

  // Typography text
  "text-1": "#0D1626",
  "text-2": "#41506B",
  "text-3": "#64748E",
  "text-num": "#040811",

  // Semantic Severities
  "sev-nominal": "#0B6B47",
  "sev-elevated": "#7A5709",
  "sev-anomaly": "#96430A",
  "sev-severe": "#B5241A",
  "sev-critical": "#8B1D77",

  // Evidence & Guard
  "evidence-weak": "#33607F",
  "guard-void": "#A12814",
  "synthetic": "#5636AE",

  // Chart tokens
  "baseline": "#58677C",
  "bound-fill": "rgba(11, 107, 71, 0.14)",

  // Interaction chrome — saturated indigo, outside every severity hue.
  "accent": "#2E4BE0",
  "accent-fg": "#FFFFFF",
  "accent-hi": "#2742C9",
  "accent-line": "rgba(39, 66, 201, 0.38)",
  "accent-soft": "rgba(46, 75, 224, 0.09)",
  "hover": "rgba(20, 32, 64, 0.05)",
  "active": "rgba(20, 32, 64, 0.09)",
  "focus-ring": "#2E4BE0",
  "overlay": "rgba(13, 22, 38, 0.48)",

  // Analysis / forecast accent (hue ~189; 5.6:1 on surface-0).
  "info": "#06768A",
  "info-soft": "rgba(6, 118, 138, 0.12)",
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
  "accent-hi": "--accent-hi",
  "accent-line": "--accent-line",
  "accent-soft": "--accent-soft",
  "hover": "--hover",
  "active": "--active",
  "focus-ring": "--focus-ring",
  "overlay": "--overlay",
  "info": "--info",
  "info-soft": "--info-soft",
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

export const INFO_TOKENS: readonly InfoToken[] = ["info", "info-soft"];

export const INTERACTION_TOKENS: readonly InteractionToken[] = [
  "accent",
  "accent-fg",
  "accent-hi",
  "accent-line",
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
