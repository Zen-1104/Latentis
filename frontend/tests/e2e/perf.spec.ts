/**
 * Table performance: largest lot page loads within budget with zero console
 * errors. No virtualization library — measurements decide, per the task.
 */
import { test, expect } from "@playwright/test";
import { api, watchConsole, expectQuiet } from "./helpers";

test("largest lot renders within budget", async ({ page }) => {
  const errors = watchConsole(page);
  const lots = await api<Array<{ lot_id: string; n_parts: number }>>("/lots");
  const biggest = lots.reduce((a, b) => (a.n_parts >= b.n_parts ? a : b));
  expect(biggest.n_parts).toBeGreaterThan(200);

  const t0 = Date.now();
  await page.goto(`#/lots/${encodeURIComponent(biggest.lot_id)}`);
  await expect(page.getByTestId("s2-dist-ready")).toBeVisible({ timeout: 120000 });
  // Chamber map is the heaviest DOM: one cell per part.
  await expect(page.getByTestId("s2-chamber-map")).toBeVisible({ timeout: 60000 });
  const cells = await page.locator("[data-testid^='s2-chamber-map-cell-']").count();
  expect(cells).toBe(biggest.n_parts);
  const ms = Date.now() - t0;
  console.log(`lot ${biggest.lot_id} n=${biggest.n_parts} interactive in ${ms}ms`);
  expect(ms).toBeLessThan(90000);
  expectQuiet(errors);
});
