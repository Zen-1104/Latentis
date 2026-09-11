/**
 * Severity and Verdict Encoding Tokens for LATENTIS (SIH26170)
 * 
 * Strict implementation of docs/UI_DESIGN_SYSTEM.md § 2, § 8.
 * 
 * Non-Negotiables:
 * 1. Severity is NEVER encoded by colour alone (TEST-A11Y-001). Every verdict
 *    carries a glyph and a word label.
 * 2. --sev-critical is violet (#8E2B7A / #7B2169), not deeper red.
 * 3. --evidence-weak is blue (#5B7C9E / #456482), not red.
 * 4. A small fixed glyph set, always paired with text in rendering.
 */

import type {
  SeverityLevel,
  SeverityConfig,
  VerdictString,
  GlyphSymbol,
  GlyphName,
} from "./types";

/**
 * Authoritative glyph symbol set per UI_DESIGN_SYSTEM § 8.
 */
export const GLYPHS: Readonly<Record<GlyphName, GlyphSymbol>> = Object.freeze({
  PASS: "✓",
  FAIL: "✗",
  ELEVATED: "△",
  RISING: "▲",
  FALLING: "▼",
  ABSOLUTE_FAIL: "◆",
  GUARD_WARNING: "!",
  WEAK_EVIDENCE: "≈",
  INVESTIGATE: "⌕",
  RETEST: "↻",
});

/** Human-readable descriptive text for each glyph for aria-labels */
export const GLYPH_LABELS: Readonly<Record<GlyphSymbol, string>> = Object.freeze({
  "✓": "Pass",
  "✗": "Fail",
  "△": "Slightly unusual",
  "▲": "Unusual / rising trend",
  "▼": "Falling trend",
  "◆": "Absolute limit failure",
  "!": "Guard warning",
  "≈": "Weak evidence / Censored data",
  "⌕": "Investigate",
  "↻": "Retest recommended",
});

/**
 * Authoritative mapping of the 5 severity tiers.
 * Each configuration contains the semantic level, display label, glyph, CSS variable,
 * and Tailwind styling classes.
 */
export const SEVERITY_CONFIGS: Readonly<Record<SeverityLevel, SeverityConfig>> = Object.freeze({
  nominal: {
    level: "nominal",
    label: "NOMINAL",
    glyph: "✓",
    altGlyphs: ["✓"],
    token: "sev-nominal",
    cssVar: "--sev-nominal",
    description: "NOMINAL / SAFE / PASS",
    tailwindBg: "bg-sev-nominal",
    tailwindText: "text-sev-nominal",
    tailwindBorder: "border-sev-nominal",
  },
  elevated: {
    level: "elevated",
    label: "ELEVATED",
    glyph: "△",
    altGlyphs: ["△"],
    token: "sev-elevated",
    cssVar: "--sev-elevated",
    description: "ELEVATED / WATCH",
    tailwindBg: "bg-sev-elevated",
    tailwindText: "text-sev-elevated",
    tailwindBorder: "border-sev-elevated",
  },
  anomaly: {
    level: "anomaly",
    label: "ANOMALOUS",
    glyph: "▲",
    altGlyphs: ["▲", "⌕"],
    token: "sev-anomaly",
    cssVar: "--sev-anomaly",
    description: "ANOMALOUS / EARLY_WARNING",
    tailwindBg: "bg-sev-anomaly",
    tailwindText: "text-sev-anomaly",
    tailwindBorder: "border-sev-anomaly",
  },
  severe: {
    level: "severe",
    label: "SEVERE",
    glyph: "✗",
    altGlyphs: ["✗"],
    token: "sev-severe",
    cssVar: "--sev-severe",
    description: "SEVERE / REJECT / FAIL",
    tailwindBg: "bg-sev-severe",
    tailwindText: "text-sev-severe",
    tailwindBorder: "border-sev-severe",
  },
  critical: {
    level: "critical",
    label: "ABSOLUTE_FAIL",
    glyph: "◆",
    altGlyphs: ["◆"],
    token: "sev-critical",
    cssVar: "--sev-critical",
    description: "ABSOLUTE_FAIL (hard limit breach; violet hue)",
    tailwindBg: "bg-sev-critical",
    tailwindText: "text-sev-critical",
    tailwindBorder: "border-sev-critical",
  },
});

/**
 * Data-quality & guard tokens configuration
 */
export const EVIDENCE_WEAK_CONFIG = Object.freeze({
  token: "evidence-weak" as const,
  label: "WEAK EVIDENCE",
  glyph: "≈" as GlyphSymbol,
  cssVar: "--evidence-weak",
  description: "Data-quality / reduced_power / censored (blue family, never red)",
  tailwindBg: "bg-evidence-weak",
  tailwindText: "text-evidence-weak",
  tailwindBorder: "border-evidence-weak",
});

export const GUARD_VOID_CONFIG = Object.freeze({
  token: "guard-void" as const,
  label: "GUARANTEE VOID",
  glyph: "!" as GlyphSymbol,
  cssVar: "--guard-void",
  description: "Guarantee VOID banner",
  tailwindBg: "bg-guard-void",
  tailwindText: "text-guard-void",
  tailwindBorder: "border-guard-void",
});

export const SYNTHETIC_BADGE_CONFIG = Object.freeze({
  token: "synthetic" as const,
  label: "SYNTHETIC DATA",
  cssVar: "--synthetic",
  description: "Non-dismissible synthetic data marker (FR-508 / INV-3)",
  tailwindBg: "bg-synthetic",
  tailwindText: "text-text-num",
  tailwindBorder: "border-synthetic",
});

/**
 * Maps any standard verdict string into its severity level and authoritative
 * display encoding (word + glyph + styling).
 * 
 * Enforces Non-negotiable 1: Severity is never encoded by colour alone.
 */
export function resolveVerdict(verdict: VerdictString): SeverityConfig {
  switch (verdict) {
    case "PASS":
    case "SAFE":
    case "NOMINAL":
      return SEVERITY_CONFIGS.nominal;

    case "WATCH":
    case "ELEVATED":
      return SEVERITY_CONFIGS.elevated;

    case "ANOMALOUS":
    case "EARLY_WARNING":
      return SEVERITY_CONFIGS.anomaly;

    case "REJECT":
    case "FAIL":
    case "SEVERE":
      return SEVERITY_CONFIGS.severe;

    case "ABSOLUTE_FAIL":
      return SEVERITY_CONFIGS.critical;
  }
}
