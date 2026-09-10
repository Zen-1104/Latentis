/**
 * J4 — Engineer decision + report: CONCUR, OVERRIDE-requires-reason, DEFER,
 * receipt, HTML report, PDF fallback behaviour. Runs on the healthy part so
 * J1's escape-part dispositions are untouched (append-only log either way).
 */
import { test, expect, request } from "@playwright/test";
import { demoParts, watchConsole, expectQuiet } from "./helpers";

test("J4 disposition contract and report path", async ({ page }) => {
  const dp = demoParts();
  expect(dp.healthy, "setup must resolve a healthy part").not.toBe(null);
  if (dp.healthy === null) return;
  const errors = watchConsole(page);
  const id = dp.healthy.componentId;

  await page.goto(`#/components/${encodeURIComponent(id)}/dispose`);
  await expect(page.getByTestId("s8-decision")).toBeVisible();

  await test.step("OVERRIDE without reason is refused with the contract message", async () => {
    await page.getByTestId("disposition-override").click();
    await page.getByTestId("disposition-reason").fill("");
    await page.getByTestId("disposition-submit").click();
    await expect(page.getByTestId("disposition-error")).toContainText("FR-409");
  });

  await test.step("OVERRIDE with reason records a receipt", async () => {
    await page.getByTestId("disposition-reason").fill("J4 E2E: override with stated reason.");
    await page.getByTestId("disposition-submit").click();
    const receipt = page.getByTestId("disposition-receipt");
    await expect(receipt).toBeVisible({ timeout: 60000 });
    await expect(receipt).toContainText("OVERRIDE");
    await expect(receipt).toContainText(/[0-9a-f]{32}/);
  });

  await test.step("DEFER records a receipt", async () => {
    await page.getByTestId("disposition-defer").click();
    await page.getByTestId("disposition-reason").fill("J4 E2E: defer for retest.");
    await page.getByTestId("disposition-submit").click();
    const receipt = page.getByTestId("disposition-receipt");
    await expect(receipt).toContainText("DEFER");
  });

  await test.step("HTML report generates; PDF follows the documented behaviour", async () => {
    await page.getByTestId("report-create").click();
    const receipt = page.getByTestId("report-receipt");
    await expect(receipt).toBeVisible({ timeout: 120000 });
    const reportId = (await receipt.innerText()).match(/[0-9a-f]{32}/)?.[0];
    expect(reportId).toBeDefined();
    if (reportId === undefined) return;
    const ctx = await request.newContext();
    const pdf = await ctx.get(`http://127.0.0.1:8000/api/v1/reports/${reportId}/pdf`);
    if (pdf.status() === 200) {
      expect(pdf.headers()["content-type"]).toContain("application/pdf");
    } else {
      // Documented fallback: 503 naming the renderer (no Chromium here).
      expect(pdf.status()).toBe(503);
      const body = (await pdf.json()) as { error: { code: string } };
      expect(body.error.code).toBe("MODEL_UNAVAILABLE");
    }
    await ctx.dispose();
  });

  expectQuiet(errors);
});
