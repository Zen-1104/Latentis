/**
 * Selection & context regression suite (final functional pass).
 * Every sidebar destination must offer a real selection path; context must
 * survive refresh and back/forward; reserved words must never become ids.
 */
import { test, expect, type Page } from "@playwright/test";
import { demoParts, expectNoFabrication } from "./helpers";

async function pickFirstComponent(page: Page, prefix: string): Promise<string> {
  await page.getByTestId(`${prefix}-picker-lot-select`).selectOption({ index: 1 });
  const list = page.getByTestId(`${prefix}-picker-list`);
  await expect(list).toBeVisible({ timeout: 30000 });
  const first = list.locator("button").first();
  const testId = (await first.getAttribute("data-testid")) ?? "";
  const id = testId.split("-select-").slice(1).join("-select-");
  expect(id).toMatch(/^C-/);
  await first.click();
  return id;
}

test("S2 sidebar selects a real lot; S1→S2 preserves the lot id", async ({ page }) => {
  await page.goto("#/");
  await expect(page.getByTestId("s1-lot-table")).toBeVisible({ timeout: 120000 });
  await page.getByTestId("nav-s2").click();
  await expect(page.getByTestId("s2-picker-table")).toBeVisible({ timeout: 30000 });
  const explore = page.locator("[data-testid^='s2-picker-select-']").first();
  const lotId = ((await explore.getAttribute("data-testid")) ?? "").replace("s2-picker-select-", "");
  expect(lotId).toMatch(/^L-/);
  await explore.click();
  await expect(page).toHaveURL(new RegExp(`#/lots/${lotId}`));
  await expect(page.getByTestId("s2-dist-ready")).toBeVisible({ timeout: 120000 });
  // Refresh keeps the lot context from the route.
  await page.reload();
  await expect(page.getByTestId("s2-dist-ready")).toBeVisible({ timeout: 120000 });
  await expectNoFabrication(page);
});

test("S3 sidebar selects a real component; S2→S3 preserves the id", async ({ page }) => {
  const dp = demoParts();
  await page.goto("#/components/");
  const id = await pickFirstComponent(page, "s3");
  await expect(page).toHaveURL(new RegExp(`#/components/${encodeURIComponent(id)}`));
  await expect(page.getByTestId("s3-why")).not.toBeEmpty({ timeout: 60000 });
  // S2 signal member navigates to the same component route.
  await page.goto(`#/lots/${dp.lotId}`);
  await expect(page.getByTestId("s2-dist-ready")).toBeVisible({ timeout: 120000 });
  const sig = page.locator("[data-testid='s2-signal-table'] tbody tr button").first();
  if ((await sig.count()) > 0) {
    const label = ((await sig.innerText()) ?? "").trim();
    await sig.click();
    await expect(page).toHaveURL(new RegExp(`#/components/${encodeURIComponent(label)}`));
    await expect(page.getByTestId("s3-why")).not.toBeEmpty({ timeout: 60000 });
  }
  await expectNoFabrication(page);
});

test("S4 sidebar selects a component; S3→S4 preserves the id", async ({ page }) => {
  const dp = demoParts();
  expect(dp.escape, "setup must resolve escape").not.toBe(null);
  if (dp.escape === null) return;
  await page.goto("#/components//drift");
  const id = await pickFirstComponent(page, "s4");
  await expect(page).toHaveURL(new RegExp(`#/components/${encodeURIComponent(id)}/drift`));
  await expect(page.getByTestId("s4-shape")).toBeVisible({ timeout: 60000 });
  // S3 cross-link carries the same id.
  await page.goto(`#/components/${dp.escape.componentId}`);
  await expect(page.getByTestId("s3-goto-drift")).toBeVisible({ timeout: 60000 });
  await page.getByTestId("s3-goto-drift").click();
  await expect(page).toHaveURL(
    new RegExp(`#/components/${encodeURIComponent(dp.escape.componentId)}/drift`),
  );
  await expect(page.getByTestId("s4-shape")).toBeVisible({ timeout: 60000 });
  await expectNoFabrication(page);
});

test("S8 sidebar selects a component; S3→S8 preserves the id", async ({ page }) => {
  const dp = demoParts();
  expect(dp.escape, "setup must resolve escape").not.toBe(null);
  if (dp.escape === null) return;
  await page.goto("#/components//dispose");
  const id = await pickFirstComponent(page, "s8");
  await expect(page).toHaveURL(new RegExp(`#/components/${encodeURIComponent(id)}/dispose`));
  await expect(page.getByTestId("s8-decision")).toBeVisible({ timeout: 60000 });
  // S8 refresh keeps the component context.
  await page.reload();
  await expect(page.getByTestId("s8-decision")).toBeVisible({ timeout: 60000 });
  // S3 cross-link carries the same id.
  await page.goto(`#/components/${dp.escape.componentId}`);
  await expect(page.getByTestId("s3-goto-dispose")).toBeVisible({ timeout: 60000 });
  await page.getByTestId("s3-goto-dispose").click();
  await expect(page).toHaveURL(
    new RegExp(`#/components/${encodeURIComponent(dp.escape.componentId)}/dispose`),
  );
  await expect(page.getByTestId("s8-decision")).toBeVisible({ timeout: 60000 });
  await expectNoFabrication(page);
});

test("adversarial routes render selection/error, emit zero garbage requests", async ({ page }) => {
  const garbage: string[] = [];
  page.on("request", (r) => {
    const path = r.url().split("/api/v1")[1] ?? "";
    if (
      /\/components\/(drift|dispose|undefined|null)\/investigation/.test(path) ||
      /\/lots\/(undefined|null)(\?|$)/.test(path)
    ) {
      garbage.push(`${r.method()} ${path}`);
    }
  });
  for (const hash of [
    "#/lots/",
    "#/lots/undefined",
    "#/lots/null",
    "#/components/",
    "#/components/undefined",
    "#/components/null",
    "#/components/drift",
    "#/components/dispose",
    "#/components//drift",
    "#/components//dispose",
  ]) {
    await page.goto(hash);
    await expect(page.locator("main").first()).not.toBeEmpty({ timeout: 30000 });
  }
  // Genuinely unknown ids are structured errors, not blanks.
  await page.goto("#/lots/NO-SUCH-LOT");
  await expect(page.getByTestId("s2-dist-error")).toContainText("UNKNOWN_LOT", { timeout: 30000 });
  expect(garbage).toEqual([]);
  await expectNoFabrication(page);
});

test("back/forward across S1→S2→S3→S4 keeps context", async ({ page }) => {
  const dp = demoParts();
  expect(dp.escape, "setup must resolve escape").not.toBe(null);
  if (dp.escape === null) return;
  await page.goto("#/");
  await expect(page.getByTestId("s1-lot-table")).toBeVisible({ timeout: 120000 });
  await page.goto(`#/lots/${dp.escape.lotId}`);
  await expect(page.getByTestId("s2-dist-ready")).toBeVisible({ timeout: 120000 });
  await page.goto(`#/components/${dp.escape.componentId}`);
  await expect(page.getByTestId("s3-why")).not.toBeEmpty({ timeout: 60000 });
  await page.goto(`#/components/${dp.escape.componentId}/drift`);
  await expect(page.getByTestId("s4-shape")).toBeVisible({ timeout: 60000 });
  await page.goBack();
  await expect(page.getByTestId("s3-why")).not.toBeEmpty({ timeout: 60000 });
  await page.goBack();
  await expect(page.getByTestId("s2-dist-ready")).toBeVisible({ timeout: 120000 });
  await page.goForward();
  await expect(page.getByTestId("s3-why")).not.toBeEmpty({ timeout: 60000 });
  await page.goForward();
  await expect(page.getByTestId("s4-shape")).toBeVisible({ timeout: 60000 });
});
