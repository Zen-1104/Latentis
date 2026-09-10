/**
 * RT-012 lite — UI ↔ API numeric agreement for sampled values.
 * Rendered text vs the same-test payload via the imported shared formatter.
 */
import { test, expect } from "@playwright/test";
import { demoParts, api, fmt, expectNoFabrication } from "./helpers";
import type { InvestigationData } from "../../src/api/generated/client";
import type { TracedValueSchema } from "../../src/api/generated/client";

function traced(v: unknown): TracedValueSchema | null {
  if (v !== null && typeof v === "object" && "value" in v && "display_precision" in v)
    return v as TracedValueSchema;
  return null;
}

test("sampled S3 numbers agree with the API payload", async ({ page }) => {
  const dp = demoParts();
  expect(dp.escape, "setup must resolve escape").not.toBe(null);
  if (dp.escape === null) return;
  const inv = await api<InvestigationData>(
    `/components/${encodeURIComponent(dp.escape.componentId)}/investigation`,
  );
  const worstParam = inv.worst?.parameter;
  const block = inv.parameters?.find((p) => p.parameter === worstParam);
  expect(block).toBeDefined();
  if (block === undefined) return;

  await page.goto(`#/components/${encodeURIComponent(dp.escape.componentId)}`);
  await expect(page.getByTestId("s3-narrative")).not.toBeEmpty({ timeout: 60000 });

  const limit = traced(block.dpat?.limit_high);
  if (limit !== null) {
    await expect(page.getByTestId("metric-s3-limit-high")).toContainText(fmt(limit));
  }
  const z = traced(block.dpat?.z);
  if (z !== null) {
    await expect(page.getByTestId("metric-s3-dpat-z")).toContainText(fmt(z));
  }
  const risk = traced(inv.risk?.risk_index);
  if (risk !== null) {
    await expect(page.getByTestId("metric-risk-total")).toContainText(fmt(risk));
  }
  // Provenance appendix covers every referenced formula id.
  const formulas = inv.provenance?.formulas_used ?? [];
  const rows = page.locator("[data-testid='s3-formulas'] tbody tr");
  await expect(rows).toHaveCount(formulas.length);

  await expectNoFabrication(page);
});

test("ledger drawer opens from a metric with registry provenance (functional repro)", async ({
  page,
}) => {
  const dp = demoParts();
  expect(dp.escape, "setup must resolve escape").not.toBe(null);
  if (dp.escape === null) return;
  await page.goto(`#/components/${dp.escape.componentId}`);
  await expect(page.getByTestId("s3-narrative")).not.toBeEmpty({ timeout: 60000 });
  await page.getByTestId("metric-s3-limit-high").click();
  const drawer = page.getByTestId("ledger-drawer");
  await expect(drawer).toBeVisible({ timeout: 15000 });
  await expect(drawer).toContainText("median");
  await page.keyboard.press("Escape");
  await expect(drawer).not.toBeVisible({ timeout: 15000 });
});

test("chamber cell navigates to the component investigation", async ({ page }) => {
  const dp = demoParts();
  expect(dp.escape, "setup must resolve escape").not.toBe(null);
  if (dp.escape === null) return;
  await page.goto(`#/lots/${dp.escape.lotId}`);
  await expect(page.getByTestId("s2-dist-ready")).toBeVisible({ timeout: 120000 });
  const cell = page.locator("[data-testid^='s2-chamber-map-cell-']").first();
  const id = ((await cell.getAttribute("data-testid")) ?? "").replace("s2-chamber-map-cell-", "");
  expect(id).toMatch(/^C-/);
  await cell.click();
  await expect(page).toHaveURL(new RegExp(`#/components/${encodeURIComponent(id)}`));
  await expect(page.getByTestId("s3-why")).not.toBeEmpty({ timeout: 60000 });
});

test("S2 cohort table row count matches the distribution payload", async ({ page }) => {
  const dp = demoParts();
  expect(dp.escape, "setup must resolve escape").not.toBe(null);
  if (dp.escape === null) return;
  const dist = await api<{
    parameters: Array<{ parameter: string; members: Array<unknown> }>;
  }>(`/lots/${encodeURIComponent(dp.escape.lotId)}/distribution`);
  await page.goto(`#/lots/${encodeURIComponent(dp.escape.lotId)}`);
  await expect(page.getByTestId("s2-dist-ready")).toBeVisible({ timeout: 120000 });
  const first = dist.parameters[0];
  if (first !== undefined) {
    const rows = page.locator(`[data-testid='s2-strip-${first.parameter}-table'] tbody tr`);
    await expect(rows).toHaveCount(first.members.length);
  }
});
