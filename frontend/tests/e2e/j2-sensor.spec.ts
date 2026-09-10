/**
 * J2 — Sensor / data-quality distinction (truthful scope).
 *
 * Corpus census (46 flagged parts, sealed backend): 274 PART, 2 INDETERMINATE,
 * 0 SOCKET/ZONE/TESTER attributions — socket cohorts are corpus-global, so
 * per-lot socket shifts wash out and claim-defeat fires. The full
 * "protected part" scenario is therefore NOT exercisable against this
 * dataset, and this spec does not fabricate it. It proves the strongest
 * truthful state: the UI renders setup evidence WITHOUT collapsing it into
 * a component verdict, and the backend recommendation passes through
 * verbatim.
 */
import { test, expect } from "@playwright/test";
import { demoParts, api, watchConsole, expectQuiet, expectNoFabrication } from "./helpers";
import type { InvestigationData } from "../../src/api/generated/client";

test("J2 sensor/data-quality evidence stays distinct from component verdict", async ({ page }) => {
  const dp = demoParts();
  const errors = watchConsole(page);
  const target = dp.sensor ?? dp.sensorIndet ?? dp.escape;
  expect(target, "setup needs escape, sensor, or sensorIndet resolved").not.toBe(null);
  if (target === null) return;
  const componentId = target.componentId;

  const inv = await api<InvestigationData>(
    `/components/${encodeURIComponent(componentId)}/investigation`,
  );

  await page.goto(`#/components/${encodeURIComponent(componentId)}`);
  await expect(page.getByTestId("s3-narrative")).not.toBeEmpty();

  await test.step("attribution state is explicit, never a generic FAIL", async () => {
    await expect(page.getByTestId("s3-attribution")).toBeVisible();
    // Evidence table carries the competing setup offsets (backend values).
    await expect(page.getByTestId("s3-attribution-evidence")).toBeVisible();
    const evidenceText = await page.getByTestId("s3-attribution-evidence").innerText();
    expect(evidenceText).toContain("socket");
  });

  await test.step("quality and CUSUM sensor-health evidence visible", async () => {
    await expect(page.getByTestId("s3-quality")).toBeVisible();
    const qualityText = await page.getByTestId("s3-quality").innerText();
    expect(qualityText).toMatch(/quality|CUSUM/i);
  });

  await test.step("recommendation passes through verbatim from the backend", async () => {
    const action = inv.recommendation?.action ?? "";
    expect(action).not.toBe("");
    await expect(page.getByTestId("s3-disposition")).toContainText(action);
  });

  await test.step("setup-attributed branch (only when the corpus provides one)", async () => {
    if (dp.sensor !== null) {
      await expect(page.getByTestId("s3-attribution")).toContainText(dp.sensor.attribution);
    } else {
      // Documented limitation: no SOCKET/ZONE/TESTER verdict on this seed.
      expect(dp.sensorIndet !== null || dp.escape !== null).toBe(true);
    }
  });

  await expectNoFabrication(page);
  expectQuiet(errors);
});
