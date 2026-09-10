/**
 * Design Token Type Definitions for LATENTIS (SIH26170)
 * 
 * Strict TypeScript types for all color, typography, spacing,
 * severity, density, and chart tokens per docs/UI_DESIGN_SYSTEM.md.
 */

/** Themes supported by LATENTIS */
export type Theme = "dark" | "light";

/** Surface tokens: page background and nested panel elevations */
export type SurfaceToken =
  | "surface-0"
  | "surface-1"
  | "surface-2"
  | "surface-3";

/** Border tokens: hairline and emphasized rules */
export type BorderToken =
  | "border-1"
  | "border-2";

/** Typography text color tokens */
export type TextToken =
  | "text-1"
  | "text-2"
  | "text-3"
  | "text-num";

/** Five semantic severity tokens. Note: sev-critical is violet, not deeper red. */
export type SeverityToken =
  | "sev-nominal"
  | "sev-elevated"
  | "sev-anomaly"
  | "sev-severe"
  | "sev-critical";

/** Dedicated data-quality / power / censoring token (blue family, never red) */
export type EvidenceToken = "evidence-weak";

/** Guarantee VOID / degradation banner token */
export type GuardToken = "guard-void";

/** Unremovable synthetic data badge token */
export type SyntheticToken = "synthetic";

/** Chart specific color tokens */
export type ChartColorToken =
  | "baseline"
  | "bound-fill";

/**
 * Interaction-chrome tokens.
 *
 * Deliberately achromatic: the charter reserves hue for severity, so
 * "this is interactive / focused / selected" must never borrow a verdict
 * colour. A green focus ring reads as PASS; a neutral one reads as focus.
 */
export type InteractionToken =
  | "accent"
  | "accent-fg"
  | "accent-soft"
  | "hover"
  | "active"
  | "focus-ring"
  | "overlay";

/** Complete union of all authorized color tokens */
export type ColorToken =
  | SurfaceToken
  | BorderToken
  | TextToken
  | SeverityToken
  | EvidenceToken
  | GuardToken
  | SyntheticToken
  | ChartColorToken
  | InteractionToken;

/** 4px base spacing scale tokens */
export type SpacingToken =
  | "sp-1"
  | "sp-2"
  | "sp-3"
  | "sp-4"
  | "sp-5"
  | "sp-6"
  | "sp-7"
  | "sp-8"
  | "sp-12";

/** Spacing steps (numbers corresponding to 4px multiples) */
export type SpacingStep = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 12;

/** Radius tokens */
export type RadiusToken = "r-sm" | "r-md" | "r-lg";

/** Radius size labels */
export type RadiusSize = "sm" | "md" | "lg";

/**
 * Shadow tokens. Panels use borders, never shadows; elevation is reserved
 * for surfaces that genuinely float above the page (drawer, popover) and
 * for sticky table headers, which need a hairline to separate from the
 * rows scrolling beneath them.
 */
export type ShadowToken = "sh-drawer" | "sh-popover" | "sh-sticky";

/** Font size scale tokens */
export type FontSizeToken =
  | "display"
  | "h1"
  | "h2"
  | "body"
  | "num"
  | "num-lg"
  | "caption"
  | "formula";

/** Font family tokens */
export type FontFamilyToken = "sans" | "mono";

/** The five discrete severity levels */
export type SeverityLevel =
  | "nominal"
  | "elevated"
  | "anomaly"
  | "severe"
  | "critical";

/** Standard verdict strings from the backend and anomaly models */
export type VerdictString =
  | "NOMINAL"
  | "SAFE"
  | "PASS"
  | "ELEVATED"
  | "WATCH"
  | "ANOMALOUS"
  | "EARLY_WARNING"
  | "SEVERE"
  | "REJECT"
  | "FAIL"
  | "ABSOLUTE_FAIL";

/** Fixed glyph set per UI_DESIGN_SYSTEM § 8 */
export type GlyphSymbol =
  | "✓"
  | "✗"
  | "▲"
  | "▼"
  | "◆"
  | "!"
  | "≈"
  | "⌕"
  | "↻";

/** Semantic names for glyphs */
export type GlyphName =
  | "PASS"
  | "FAIL"
  | "RISING"
  | "FALLING"
  | "ABSOLUTE_FAIL"
  | "GUARD_WARNING"
  | "WEAK_EVIDENCE"
  | "INVESTIGATE"
  | "RETEST";

/** Density modes for data tables per UI_DESIGN_SYSTEM § 9 */
export type DensityMode = "comfortable" | "compact";

/** Comprehensive severity configuration object */
export interface SeverityConfig {
  readonly level: SeverityLevel;
  readonly label: string;
  readonly glyph: GlyphSymbol;
  readonly altGlyphs: readonly GlyphSymbol[];
  readonly token: SeverityToken;
  readonly cssVar: string;
  readonly description: string;
  readonly tailwindBg: string;
  readonly tailwindText: string;
  readonly tailwindBorder: string;
}

/** Typography configuration descriptor */
export interface FontSizeConfig {
  readonly size: string;
  readonly lineHeight: string;
  readonly tabular?: boolean;
  readonly mono?: boolean;
  readonly use: string;
}

/** Table density mode configuration */
export interface DensityConfig {
  readonly mode: DensityMode;
  readonly rowHeightPx: number;
  readonly cellPaddingY: string;
  readonly label: string;
  readonly description: string;
}
