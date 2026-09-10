/**
 * Spacing, Radius, and Elevation Tokens for LATENTIS (SIH26170)
 * 
 * Strict implementation of docs/UI_DESIGN_SYSTEM.md § 4.
 * 
 * Rules:
 * 1. 4px base scale strictly maintained (sp-1 through sp-12).
 * 2. Radius is restrained (max 8px) — this is instrumentation, not consumer SaaS.
 * 3. Panels use borders, not shadows. Elevation shadows are reserved for surfaces that
 *    genuinely float: the drawer, popovers, and sticky table headers.
 * 4. Control heights are tokenised so every button, input, select and chip in the app
 *    lands on the same baseline — the locked 4px scale gives no half-steps, so padding
 *    alone cannot produce a consistent control rhythm.
 */

import type {
  SpacingStep,
  RadiusSize,
  ShadowToken,
  Theme,
} from "./types";

/** 4px base spacing scale mapping */
export const SPACING_PIXELS: Readonly<Record<SpacingStep, number>> = Object.freeze({
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  7: 28,
  8: 32,
  12: 48,
});

/** Spacing token CSS variable names */
export const SPACING_CSS_VARS: Readonly<Record<SpacingStep, string>> = Object.freeze({
  1: "--sp-1",
  2: "--sp-2",
  3: "--sp-3",
  4: "--sp-4",
  5: "--sp-5",
  6: "--sp-6",
  7: "--sp-7",
  8: "--sp-8",
  12: "--sp-12",
});

/** Radius token pixel values */
export const RADIUS_PIXELS: Readonly<Record<RadiusSize, number>> = Object.freeze({
  sm: 3,
  md: 5,
  lg: 8,
});

/** Radius CSS variable names */
export const RADIUS_CSS_VARS: Readonly<Record<RadiusSize, string>> = Object.freeze({
  sm: "--r-sm",
  md: "--r-md",
  lg: "--r-lg",
});

/** Elevation shadows */
export const SHADOW_VALUES: Readonly<Record<Theme, Record<ShadowToken, string>>> = Object.freeze({
  dark: {
    "sh-drawer": "-4px 0 24px rgba(0, 0, 0, 0.4)",
    "sh-popover": "0 4px 16px rgba(0, 0, 0, 0.3)",
    "sh-sticky": "0 1px 0 rgba(0, 0, 0, 0.5)",
  },
  light: {
    "sh-drawer": "-4px 0 24px rgba(15, 23, 42, 0.15)",
    "sh-popover": "0 4px 16px rgba(15, 23, 42, 0.12)",
    "sh-sticky": "0 1px 0 rgba(15, 23, 42, 0.1)",
  },
});

/** Control size labels — one baseline for every interactive element. */
export type ControlSize = "sm" | "md" | "lg";

/**
 * Tokenised control heights. The locked spacing scale has no half-steps, so
 * `py-1.5`-style padding silently resolves to nothing; controls declare an
 * explicit height and centre their content instead.
 */
export const CONTROL_HEIGHT_PIXELS: Readonly<Record<ControlSize, number>> = Object.freeze({
  sm: 28,
  md: 34,
  lg: 40,
});

/** Height of an inline chip (severity chips, metadata badges). */
export const CHIP_HEIGHT_PIXELS = 22;

/**
 * Returns CSS var expression for spacing step (e.g. `var(--sp-4, 16px)`).
 */
export function getSpacingVar(step: SpacingStep): string {
  const cssVar = SPACING_CSS_VARS[step];
  const px = SPACING_PIXELS[step];
  return `var(${cssVar}, ${px}px)`;
}

/**
 * Returns CSS var expression for radius size (e.g. `var(--r-md, 5px)`).
 */
export function getRadiusVar(size: RadiusSize): string {
  const cssVar = RADIUS_CSS_VARS[size];
  const px = RADIUS_PIXELS[size];
  return `var(${cssVar}, ${px}px)`;
}

/**
 * Returns CSS var expression for elevation shadow.
 */
export function getShadowVar(token: ShadowToken): string {
  const cssVar = `--${token}`;
  const fallback = SHADOW_VALUES.dark[token];
  return `var(${cssVar}, ${fallback})`;
}
