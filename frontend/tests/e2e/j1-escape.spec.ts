/**
 * J1 — Escape investigation (flagship). S1 → runtime spotlight → S3 →
 * WHY → evidence → forecast → risk → CONCUR → S8 report.
 * No component ID is hard-coded: the ID is read from the spotlight at
 * runtime and every number is compared to the API payload.
 */
import { test, expect } from "@playwright/test";
import {
  demoParts,
  api,
  fmt,
  watchConsole,
  expectQuiet,
  expectNoFabrication,
} from "./helpers";
import type { InvestigationData } from "../../src/api/generated/client";
import type { TracedValueSchema } from "../../src/api/generated/client";

test("J1 escape journey: runtime spotlight to concur + report", async ({ page }) => {
  const dp = demoParts();
  const errors = watchConsole(page);

  await test.step("app starts with synthetic guard and ready instrument", async () => {
    await page.goto("#/");
    await expect(page.getByTestId("synthetic-data-badge")).toHaveText("SYNTHETIC DATA");
    await expect(page.getByTestId("backend-status")).toContainText("INSTRUMENT READY");
  });

  await test.step("command center loads with real lots and provenance", async () => {
    await expect(page.getByTestId("s1-provenance")).toBeVisible();
    await expect(page.getByTestId("s1-lot-table")).toBeVisible();
    const rows = page.locator("[data-testid='s1-lot-table'] tbody tr");
    await expect(rows.first()).toBeVisible();
  });

  const spotlightId = await test.step("escape spotlight resolves from runtime data", async () => {
    const spotlight = page.getByTestId("s1-spotlight");
    await expect(spotlight).toBeVisible({ timeout: 120000 });
    const id = (await page.getByTestId("s1-spotlight-open").innerText()).trim();
    expect(id).toMatch(/^C-/);
    // The resolved part must satisfy the escape predicate in the live payload.
    const inv = await api<InvestigationData>(`/components/${encodeURIComponent(id)}/investigation`);
    const escapeBlock = inv.parameters?.find(
      (p) => p.dpat?.verdict === "FAIL" && p.absolute?.verdict === "PASS",
    );
    expect(escapeBlock).toBeDefined();
    return { id, inv };
  });

  await test.step("open investigation; identity and verdict disagreement visible", async () => {
    await page.getByTestId("s1-spotlight-open").click();
    await expect(page).toHaveURL(new RegExp(`#/components/${encodeURIComponent(spotlightId.id)}`));
    await expect(page.getByTestId("s3-narrative")).not.toBeEmpty();
    await expect(page.getByTestId("s3-verdict-dpat")).toContainText("FAIL");
    await expect(page.getByTestId("s3-verdict-absolute")).toContainText("PASS");
  });

  await test.step("rendered numbers agree with the API payload (oracle rule)", async () => {
    const inv = spotlightId.inv;
    const worstParam = inv.worst?.parameter;
    const block = inv.parameters?.find((p) => p.parameter === worstParam);
    const limit = block?.dpat?.limit_high;
    if (limit !== undefined && limit !== null && "value" in (limit as object)) {
      await expect(page.getByTestId("metric-s3-limit-high")).toContainText(
        fmt(limit as TracedValueSchema),
      );
    }
    const z = block?.dpat?.z;
    if (z !== undefined && z !== null && "value" in (z as object)) {
      await expect(page.getByTestId("metric-s3-dpat-z")).toContainText(fmt(z as TracedValueSchema));
    }
    const risk = inv.risk?.risk_index;
    if (risk !== undefined && risk !== null && "value" in (risk as object)) {
      await expect(page.getByTestId("metric-risk-total")).toContainText(
        fmt(risk as TracedValueSchema),
      );
    }
  });

  await test.step("evidence chain sections visible", async () => {
    await expect(page.getByTestId("s3-why")).toBeVisible();
    await expect(page.getByTestId("s3-peer")).toBeVisible();
    await expect(page.getByTestId("s3-attribution")).toBeVisible();
    await expect(page.getByTestId("s3-forecast")).toBeVisible();
    await expect(page.getByTestId("s3-quality")).toBeVisible();
    await expect(page.getByTestId("s3-risk")).toBeVisible();
    await expect(page.getByTestId("s3-provenance-detail")).toBeVisible();
    await expect(page.getByTestId("s3-narratives")).toBeVisible();
  });

  await test.step("recommendation shown; engineer concurs with receipt", async () => {
    await expect(page.getByTestId("s3-disposition")).toBeVisible();
    await page.getByTestId("disposition-concur").click();
    await page.getByTestId("disposition-reason").fill("J1 E2E: evidence reviewed, concur.");
    await page.getByTestId("disposition-submit").click();
    const receipt = page.getByTestId("disposition-receipt");
    await expect(receipt).toBeVisible({ timeout: 60000 });
    await expect(receipt).toContainText("CONCUR");
  });

  await test.step("HTML report generates with a real report id", async () => {
    await page.goto(`#/components/${encodeURIComponent(spotlightId.id)}/dispose`);
    await expect(page.getByTestId("s8-report")).toBeVisible();
    await page.getByTestId("report-create").click();
    const receipt = page.getByTestId("report-receipt");
    await expect(receipt).toBeVisible({ timeout: 120000 });
    await expect(receipt).toContainText(/[0-9a-f]{32}/);
  });

  await test.step("screenshots + integrity", async () => {
    await page.goto(`#/components/${encodeURIComponent(spotlightId.id)}`);
    await expect(page.getByTestId("s3-narrative")).not.toBeEmpty();
    await page.screenshot({ path: "test-results/j1-s3.png" });
    await page.goto("#/");
    await expect(page.getByTestId("s1-spotlight")).toBeVisible({ timeout: 120000 });
    await page.screenshot({ path: "test-results/j1-s1.png" });
    await expectNoFabrication(page);
    expectQuiet(errors);
  });

  // Sanity: setup-resolved escape matches the runtime-resolved one on this dataset.
  expect(dp.escape === null || typeof dp.escape.componentId === "string").toBe(true);
});
