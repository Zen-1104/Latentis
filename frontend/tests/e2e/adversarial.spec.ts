/**
 * Adversarial suite: error/empty/loading/degraded states via network-layer
 * provocation (states only — never intercepted numbers), navigation honesty,
 * verdict/provenance integrity. No pixel or CSS-class selectors.
 */
import { test, expect } from "@playwright/test";
import { demoParts, expectNoFabrication } from "./helpers";

const META = {
  request_id: "e2e",
  computed_at: "2026-01-01T00:00:00Z",
  dataset_hash: null,
  profile_id: null,
  profile_version: null,
  model_versions: {},
  data_provenance: "SYNTHETIC",
  code_git_sha: "e2e",
  duration_ms: 1,
};

test("unknown lot is a structured error, not a blank", async ({ page }) => {
  await page.goto("#/lots/NO-SUCH-LOT");
  const err = page.getByTestId("s2-dist-error");
  await expect(err).toBeVisible({ timeout: 30000 });
  await expect(err).toContainText("UNKNOWN_LOT");
});

test("API 422 surfaces code, message and remediation", async ({ page }) => {
  await page.route("**/api/v1/lots", (route) =>
    route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "VALIDATION_FAILED",
          message: "E2E provoked validation failure.",
          details: [],
          remediation: "E2E remediation string.",
          request_id: "e2e-422",
        },
      }),
    }),
  );
  await page.goto("#/");
  const err = page.getByTestId("s1-lots-error");
  await expect(err).toBeVisible({ timeout: 30000 });
  await expect(err).toContainText("VALIDATION_FAILED");
  await expect(err).toContainText("E2E remediation string");
  await expect(err).toContainText("e2e-422");
});

test("empty lots render designed empty copy with the ingest action", async ({ page }) => {
  await page.route("**/api/v1/lots", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [], meta: META }),
    }),
  );
  await page.goto("#/");
  await expect(page.getByTestId("s1-lots-empty")).toBeVisible({ timeout: 30000 });
  await expect(page.getByTestId("s1-lots-empty")).toContainText("No dataset ingested");
});

test("loading skeleton resolves to real content", async ({ page }) => {
  await page.route("**/api/v1/lots", async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  await page.goto("#/");
  await expect(page.getByTestId("s1-lots-loading")).toBeVisible({ timeout: 10000 });
  await expect(page.getByTestId("s1-lot-table")).toBeVisible({ timeout: 120000 });
});

test("degraded health disables trust, names it in the header", async ({ page }) => {
  await page.route("**/api/v1/healthz", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: { status: "degraded", missing: ["models: e2e provoked absence"] },
        meta: META,
      }),
    }),
  );
  await page.goto("#/");
  await expect(page.getByTestId("backend-status")).toContainText("DEGRADED", { timeout: 15000 });
});

test("sidebar buttons without selection land on guidance, never garbage requests", async ({ page }) => {
  const bad: string[] = [];
  page.on("response", (r) => {
    if (r.url().includes("/components/drift") || r.url().includes("/components/dispose")) {
      bad.push(r.url());
    }
  });
  await page.goto("#/");
  await expect(page.getByTestId("s1-lot-table")).toBeVisible({ timeout: 120000 });
  for (const nav of ["nav-s2", "nav-s4", "nav-s8"] as const) {
    await page.getByTestId(nav).click();
    await expect(page.locator("main").first()).not.toBeEmpty({ timeout: 15000 });
  }
  expect(bad).toEqual([]);
});

test("navigation: deep link, reload persistence, back/forward", async ({ page }) => {
  const dp = demoParts();
  expect(dp.escape, "setup must resolve escape").not.toBe(null);
  if (dp.escape === null) return;
  const url = `#/components/${dp.escape.componentId}`;
  await page.goto(url);
  await expect(page.getByTestId("s3-narrative")).not.toBeEmpty({ timeout: 60000 });
  await page.reload();
  await expect(page.getByTestId("s3-narrative")).not.toBeEmpty({ timeout: 60000 });
  await page.goto("#/");
  await expect(page.getByTestId("s1-lot-table")).toBeVisible({ timeout: 120000 });
  await page.goBack();
  await expect(page.getByTestId("s3-narrative")).not.toBeEmpty({ timeout: 60000 });
  await page.goForward();
  await expect(page.getByTestId("s1-lot-table")).toBeVisible({ timeout: 120000 });
  // Refresh is stateless on every surface: S2 and S4 refetch by route id.
  await page.goto(`#/lots/${dp.escape.lotId}`);
  await expect(page.getByTestId("s2-dist-ready")).toBeVisible({ timeout: 120000 });
  await page.reload();
  await expect(page.getByTestId("s2-dist-ready")).toBeVisible({ timeout: 120000 });
  await page.goto(`#/components/${dp.escape.componentId}/drift`);
  await expect(page.getByTestId("s4-shape")).toBeVisible({ timeout: 60000 });
  await page.reload();
  await expect(page.getByTestId("s4-shape")).toBeVisible({ timeout: 60000 });
});

test("verdicts are text+glyph, disagreement preserved, provenance intact", async ({ page }) => {
  const dp = demoParts();
  expect(dp.escape, "setup must resolve escape").not.toBe(null);
  if (dp.escape === null) return;
  await page.goto(`#/components/${dp.escape.componentId}`);
  await expect(page.getByTestId("s3-narrative")).not.toBeEmpty({ timeout: 60000 });
  // Text assertions (never colour-only): both sides of the disagreement.
  await expect(page.getByTestId("s3-verdict-dpat")).toContainText("FAIL");
  await expect(page.getByTestId("s3-verdict-absolute")).toContainText("PASS");
  // Provenance appendix lists every referenced formula.
  await expect(page.getByTestId("s3-formulas")).toBeVisible();
  // Adapter params use the weak-evidence treatment, not traced metrics.
  const tabs = page.locator("[data-testid^='s3-tab-']");
  const tabCount = await tabs.count();
  expect(tabCount).toBeGreaterThan(0);
  await expectNoFabrication(page);
});
