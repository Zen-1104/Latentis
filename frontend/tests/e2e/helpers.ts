/** Shared E2E helpers. Oracle rule: UI text vs API payload + shared formatter. */
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page } from "@playwright/test";
import { formatTraced } from "../../src/format";
import type { TracedValueSchema } from "../../src/api/generated/client";

export const API = "http://127.0.0.1:8000/api/v1";

export interface DemoParts {
  datasetHash: string;
  lotId: string;
  escape: { componentId: string; lotId: string; parameter: string } | null;
  healthy: { componentId: string; lotId: string } | null;
  sensor: {
    componentId: string;
    lotId: string;
    parameter: string;
    attribution: string;
    recommendation: string | null;
  } | null;
  sensorIndet: { componentId: string; lotId: string; parameter: string } | null;
  degraded: {
    componentId: string;
    lotId: string;
    kind: string;
    insufficient: boolean | null;
    recommendation: string | null;
  } | null;
}

export function demoParts(): DemoParts {
  const here = dirname(fileURLToPath(import.meta.url));
  return JSON.parse(readFileSync(join(here, ".demo-parts.json"), "utf8")) as DemoParts;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} → ${res.status}`);
  const json = (await res.json()) as { data: T };
  return json.data;
}

/** Format exactly as the app does (imported formatter — never reimplemented). */
export function fmt(traced: TracedValueSchema): string {
  return formatTraced(traced);
}

/** Collect console errors for a page; assert quiet at journey end. */
export function watchConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(String(err)));
  return errors;
}

export function expectQuiet(errors: string[]): void {
  expect(errors.filter((e) => !e.includes("favicon"))).toEqual([]);
}

/**
 * Data-integrity sweep: no fabrication markers rendered as values.
 * Word-boundary matching (documented precision): a substring scan for "nan"
 * false-positives on "provenance", so NaN is matched case-sensitively as a
 * standalone token — exactly how `String(NaN)` would render.
 */
export async function expectNoFabrication(page: Page): Promise<void> {
  const text = await page.locator("body").innerText();
  expect(text).not.toMatch(/\bNaN\b/);
  expect(text.toLowerCase()).not.toMatch(/\bundefined\b/);
}
