/**
 * Density Mode Tokens for LATENTIS (SIH26170)
 * 
 * Strict implementation of docs/UI_DESIGN_SYSTEM.md § 9.
 * 
 * Rules:
 * 1. Two modes: Comfortable (default, 40px table rows) and Compact (28px for 500-part lots).
 * 2. Both audited for >= 4.5:1 contrast and accessible hit targets.
 * 3. Persisted in localStorage as a presentation-only preference.
 */

import type { DensityMode, DensityConfig } from "./types";

/** LocalStorage key for persisting density mode preference */
export const DENSITY_STORAGE_KEY = "latentis_density_mode";

/** Default table density mode */
export const DEFAULT_DENSITY_MODE: DensityMode = "comfortable";

/** Authoritative configurations for each density mode */
export const DENSITY_CONFIGS: Readonly<Record<DensityMode, DensityConfig>> = Object.freeze({
  comfortable: {
    mode: "comfortable",
    rowHeightPx: 40,
    cellPaddingY: "var(--sp-3, 12px)",
    label: "Comfortable",
    description: "Default mode with 40px table rows for standard cohort inspection",
  },
  compact: {
    mode: "compact",
    rowHeightPx: 28,
    cellPaddingY: "var(--sp-1, 4px)",
    label: "Compact",
    description: "Dense 28px rows for high-density 500-part lots without pagination jitter",
  },
});

/**
 * Returns row height in pixels for the specified density mode.
 */
export function getRowHeightPx(mode: DensityMode = DEFAULT_DENSITY_MODE): number {
  return DENSITY_CONFIGS[mode].rowHeightPx;
}
