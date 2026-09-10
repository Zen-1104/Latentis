/**
 * Backend verdict → locked severity-token mapping.
 *
 * Every verdict renders glyph + text label + token colour (never colour
 * alone, TEST-A11Y-001). Unknown strings map to `null` so the caller
 * renders a neutral label-only chip instead of inventing a severity.
 */
import type { SeverityLevel } from "./tokens/types";

export type DisplaySeverity = SeverityLevel | "weak";

const MAP: Readonly<Record<string, DisplaySeverity>> = Object.freeze({
  NOMINAL: "nominal",
  SAFE: "nominal",
  PASS: "nominal",
  ACCEPT: "nominal",
  VALID: "nominal",
  ELEVATED: "elevated",
  WATCH: "elevated",
  MONITOR: "elevated",
  EXTEND: "elevated",
  ANOMALOUS: "anomaly",
  EARLY_WARNING: "anomaly",
  INVESTIGATE: "anomaly",
  SEVERE: "severe",
  REJECT: "severe",
  FAIL: "severe",
  ABSOLUTE_FAIL: "critical",
  // Refusal / insufficient-evidence states are blue weak-evidence, never red.
  INSUFFICIENT_EVIDENCE: "weak",
  INSUFFICIENT_DATA: "weak",
  INSUFFICIENT_COHORT: "weak",
  INSUFFICIENT_CALIBRATION: "weak",
  NO_VARIATION: "weak",
  DEGRADED: "weak",
  VOID: "weak",
  INDETERMINATE: "weak",
});

export function severityOf(value: string | null | undefined): DisplaySeverity | null {
  if (value === null || value === undefined) return null;
  return MAP[value] ?? null;
}
