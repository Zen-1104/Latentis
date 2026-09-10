/**
 * Value formatting. One rule: a decision-bearing number is formatted from
 * its own TracedValue (`value` rounded at `display_precision`, unit shown).
 * Plain backend floats (fully_traced=false adapters, D-044/D-045) are
 * formatted explicitly as plain — never dressed up as traced.
 */
import type { TracedValueSchema } from "./api/generated/client";

/** Narrow a backend value to a TracedValue. Anything else is plain. */
export function isTraced(value: unknown): value is TracedValueSchema {
  if (value === null || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v["value"] === "number" &&
    typeof v["unit"] === "string" &&
    typeof v["formula_id"] === "string" &&
    typeof v["display_precision"] === "number"
  );
}

/** Render a TracedValue exactly as the backend specifies. */
export function formatTraced(traced: TracedValueSchema): string {
  const precision = Math.max(0, Math.min(8, traced.display_precision));
  return traced.value.toFixed(precision);
}

/** Render a plain backend float with an explicit precision (adapter values). */
export function formatPlain(value: number, precision = 2): string {
  if (!Number.isFinite(value)) return "—";
  return value.toFixed(precision);
}

/** Shorten `sha256:9f2c…` for headers while keeping it identifiable. */
export function shortHash(hash: string | null | undefined, chars = 8): string {
  if (!hash) return "—";
  const bare = hash.startsWith("sha256:") ? hash.slice(7) : hash;
  if (bare.length <= chars) return bare;
  return `${bare.slice(0, chars)}…`;
}

/** Compact UTC timestamp for receipts. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().replace("T", " ").replace("Z", " UTC");
}
