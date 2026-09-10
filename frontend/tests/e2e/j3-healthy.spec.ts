/**
 * J3 — Healthy component: explicit pass state, no false alarm, provenance
 * intact. "Healthy" is backend-authoritative (all DPAT + absolute PASS).
 */
import { test, expect } from "@playwright/test";
import { demoParts, api, watchConsole, expectQuiet, expectNoFabrication } from "./helpers";
import type { InvestigationData } from "../../src/api/generated/client";

test("J3 healthy component shows explicit pass state", async ({ page }) => {
  const dp = demoParts();
  expect(dp.healthy, "setup must resolve a healthy part").not.toBe(null);
  if (dp.healthy === null) return;
  const errors = watchConsole(page);

  const inv = await api<InvestigationData>(
    `/components/${encodeURIComponent(dp.healthy.componentId)}/investigation`,
  );
  // Backend-authoritative health: every parameter passes both verdicts.
  expect(
    inv.parameters?.every((p) => p.dpat?.verdict === "PASS" && p.absolute?.verdict === "PASS"),
  ).toBe(true);

  await page.goto(`#/components/${encodeURIComponent(dp.healthy.componentId)}`);
  await expect(page.getByTestId("s3-narrative")).not.toBeEmpty();

  await expect(page.getByTestId("s3-verdict-dpat")).toContainText("PASS");
  await expect(page.getByTestId("s3-verdict-absolute")).toContainText("PASS");
  // Worst severity/band render verbatim whatever the backend reports
  // (severity is a presentation band, not the verdict — GLOSSARY D1).
  if (inv.worst?.severity !== undefined) {
    await expect(page.getByTestId("s3-worst-severity")).toContainText(inv.worst.severity);
  }
  if (inv.worst?.band !== undefined && inv.worst.band !== null) {
    await expect(page.getByTestId("s3-worst-band")).toContainText(inv.worst.band);
  }

  await expect(page.getByTestId("s3-provenance-detail")).toBeVisible();
  await expect(page.getByTestId("s3-formulas")).toBeVisible();

  await expectNoFabrication(page);
  expectQuiet(errors);
});
