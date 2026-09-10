/**
 * J5 — Degraded / insufficient-evidence honesty.
 * Single-part lot part: sealed logic recommends INSUFFICIENT_EVIDENCE and
 * the UI must render that verbatim — never override it, never invent a
 * forecast. Plus the API 422 path for unknown components.
 */
import { test, expect } from "@playwright/test";
import { demoParts, api, watchConsole, expectQuiet, expectNoFabrication } from "./helpers";
import type { InvestigationData } from "../../src/api/generated/client";

test("J5 degraded and refusal states render verbatim", async ({ page }) => {
  const dp = demoParts();
  expect(dp.degraded, "setup must resolve a degraded part").not.toBe(null);
  if (dp.degraded === null) return;
  const errors = watchConsole(page);
  const { componentId } = dp.degraded;

  const inv = await api<InvestigationData>(
    `/components/${encodeURIComponent(componentId)}/investigation`,
  );

  await page.goto(`#/components/${encodeURIComponent(componentId)}`);
  // WHY section always renders (worst-parameter layer or explicit empty copy).
  await expect(page.getByTestId("s3-why")).not.toBeEmpty();

  await test.step("sealed INSUFFICIENT_EVIDENCE recommendation renders exactly", async () => {
    expect(inv.recommendation?.action).toBe("INSUFFICIENT_EVIDENCE");
    await expect(page.getByTestId("s3-disposition")).toContainText("INSUFFICIENT_EVIDENCE");
  });

  await test.step("no forecast invented where the backend refuses", async () => {
    const bands = (inv.parameters ?? []).map((p) => p.drift?.band ?? p.band ?? null);
    // At least the refusal is visible somewhere honest: guard banner or band.
    const body = await page.locator("body").innerText();
    expect(body).toMatch(/INSUFFICIENT|insufficient|reduced|REFUSAL/i);
    expect(bands.length).toBeGreaterThan(0);
  });

  await expectNoFabrication(page);
  expectQuiet(errors);

  await test.step("unknown component is a structured 422/404, not a blank", async () => {
    errors.length = 0;
    await page.goto("#/components/NO-SUCH-PART-404");
    const err = page.getByTestId("s3-inv-error");
    await expect(err).toBeVisible({ timeout: 30000 });
    await expect(err).toContainText(/UNKNOWN_COMPONENT|NOT_FOUND|404|422/);
    // The browser logs the deliberately-provoked 404 fetch as a resource
    // error; that single message is expected, anything else is a defect.
    const rest = errors.filter((e) => !e.includes("favicon"));
    expect(rest.every((e) => e.includes("404"))).toBe(true);
  });
});
