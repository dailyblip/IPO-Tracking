import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixturePath = process.env.IPO_ROLL_PILOT_FIXTURE;
test("render captured reviewer RPC output with line-wrapped source evidence", async ({
  page,
}) => {
  test.skip(
    !fixturePath,
    "Requires private captured RPC output; never commit real source fixtures",
  );
  const d = JSON.parse(readFileSync(fixturePath!, "utf8"));
  const query = d.qa?.query || "University of Michigan";
  const matchedPerson = d.qa?.matchedPerson || "Brent Jewell";
  const holderName = d.detail.people[0].name;
  const liquidityFixture = process.env.IPO_ROLL_LIQUIDITY_FIXTURE
    ? JSON.parse(readFileSync(process.env.IPO_ROLL_LIQUIDITY_FIXTURE, "utf8")) : null;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let report: any = null;
  let generations = 0;
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/liquidity")) {
      if (route.request().method() === "POST") {
        generations++;
        report = { id: `report-${generations}`, version: "liquidity/1", asOf: "2026-09-24T17:00:00Z", method: "Evidence review; no AI inference", company: d.detail.company, person: d.detail.people[0].name, relationship: d.detail.people[0].relationship, relationshipSource: d.detail.people[0].source, positions: [], notice: "Static private snapshot. Unknown is not zero." };
        if (liquidityFixture) report = { ...liquidityFixture, id: `report-${generations}` };
      }
      return route.fulfill({ json: report });
    }
    const data =
      path === "/api/config"
        ? {
            demo: false,
            configured: true,
            url: "https://auth.example.test",
            key: "publishable",
          }
        : path === "/api/account"
          ? { email: "reviewer@example.invalid", researchAccess: true }
          : path === "/api/overview"
            ? d.overview
            : path === "/api/offerings"
              ? d.offerings
              : path === "/api/people/search"
                ? d.matches
                : path.startsWith("/api/offerings/")
                  ? d.detail
                  : { ids: [] };
    return route.fulfill({ json: data });
  });
  await page.route("https://auth.example.test/**", (route) =>
    route.fulfill({
      json: {
        access_token: "test-session",
        refresh_token: "test-refresh",
        expires_in: 3600,
        token_type: "bearer",
        user: {
          id: "50000000-0000-4000-8000-000000000001",
          email: "reviewer@example.invalid",
          aud: "authenticated",
        },
      },
    }),
  );
  await page.goto("/");
  await page.getByLabel("Email address").fill("reviewer@example.invalid");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("STAGING WORKSPACE")).toBeVisible();
  await page
    .getByRole("button", { name: "People Search", exact: true })
    .click();
  await page.getByLabel("Search biographies").fill(query);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".match-card")).toHaveCount(1);
  await expect(
    page.locator("mark").filter({ hasText: query }).first(),
  ).toBeVisible();
  await expect(page.getByText(matchedPerson).first()).toBeVisible();
  await page.screenshot({
    path: process.env.IPO_ROLL_PILOT_SCREENSHOT || "test-results/pilot.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: `Open ${d.detail.company}` })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText(holderName).first()).toBeVisible();
  await page.getByRole("button", { name: "Liquidity Analysis", exact: true }).click();
  const analysis = page.getByRole("dialog", { name: `Liquidity Analysis for ${holderName}` });
  await expect(analysis).toBeVisible();
  await expect(analysis.getByText("PRIVATE TO YOUR ACCOUNT")).toBeVisible();
  if (liquidityFixture) {
    const p = liquidityFixture.positions[0];
    await expect(analysis.getByText(p.positionBasis === 'post' ? "Projected post-offering position" : "Pre-offering position", { exact: true })).toBeVisible();
    await expect(analysis.getByText(`${p.shares.toLocaleString()} disclosed shares · Filing date ${p.filingDate || p.holdingsDate}`, { exact: true })).toBeVisible();
    await expect(analysis.getByText(`Holdings as of: ${p.holdingsAsOf || 'Not established in this snapshot'}. This is not confirmation of current holdings.`, { exact: true })).toBeVisible();
    const passages = `Source passages and footnotes (${p.evidence.length + 1})`;
    await analysis.getByText(passages, { exact: true }).click();
    await expect(analysis.getByText(p.evidence.at(-1).excerpt, { exact: true })).toBeVisible();
    await expect(analysis.getByText(/Source blocks? \d+/).first()).toBeVisible();
    await analysis.getByText(passages, { exact: true }).click();
    await expect(analysis.getByText(/Lock-up start: Not confirmed/)).toBeVisible();
    await analysis.getByText("Source document version", { exact: true }).click();
    await expect(analysis.getByText(`SEC accession: ${p.filingAccession}`)).toBeVisible();
  } else {
    await expect(analysis.getByText(/No reviewed individual stock positions/)).toBeVisible();
  }
  expect(generations).toBe(1);
  await page.keyboard.press("Escape");
  await expect(analysis).not.toBeVisible();
  await expect(page.getByRole("dialog", { name: "Company research" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Liquidity Analysis", exact: true })).toBeFocused();
  await page.getByRole("button", { name: "Liquidity Analysis", exact: true }).click();
  await expect(analysis).toBeVisible();
  await expect(analysis.getByRole("button", { name: "Refresh analysis" })).toBeEnabled();
  expect(generations).toBe(1);
  await analysis.getByRole("button", { name: "Refresh analysis" }).click();
  await expect(analysis.getByRole("button", { name: "Refresh analysis" })).toBeEnabled();
  expect(generations).toBe(2);
  await page.screenshot({path: "test-results/liquidity-report.png", fullPage: true});
  await analysis.getByRole("button", { name: "Close liquidity analysis" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Liquidity Analysis", exact: true }).click();
  await expect(analysis).toBeVisible();
  const box = await analysis.boundingBox();
  expect(box!.width).toBeLessThanOrEqual(390);
  await page.screenshot({path: "test-results/liquidity-report-mobile.png", fullPage: true});
  await analysis.getByRole("button", { name: "Close liquidity analysis" }).click();
  expect(errors).toEqual([]);
});
