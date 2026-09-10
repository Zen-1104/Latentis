/**
 * LATENTIS Design Tokens
 * 
 * Barrel export for the locked token layer per docs/UI_DESIGN_SYSTEM.md.
 * 
 * Invariants:
 * - FR-506..FR-510: Fully typed tokens for colors, typography, spacing, severity, charts.
 * - QG-FE-02: Components import semantic tokens; raw hex/spacing is a lint error.
 * - Non-negotiable 1: Severity is never encoded by colour alone.
 * - Non-negotiable 2: --sev-critical is violet, not deeper red.
 * - Non-negotiable 3: --evidence-weak is blue, not red.
 * - Non-negotiable 4: tabular-nums lining-nums on all numerals.
 */

export * from "./types";
export * from "./colors";
export * from "./typography";
export * from "./spacing";
export * from "./severity";
export * from "./density";
export * from "./charts";
