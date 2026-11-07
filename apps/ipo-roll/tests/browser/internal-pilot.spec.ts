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
  const holderName = d.qa?.holderName || d.detail.people[0].name;
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
  const holderToggle = page.locator('.person-toggle').filter({ hasText: holderName });
  await expect(holderToggle).toBeVisible();
  if (await holderToggle.getAttribute('aria-expanded') !== 'true') await holderToggle.click();
  if (d.detail.people.find((p: any) => p.name === holderName)?.relationship === 'Footnote controller') {
    await expect(page.locator('.person-toggle')).toHaveCount(d.detail.people.length);
    await expect(page.getByText('Named fund/control relationship · personal economic ownership not established.')).toBeVisible();
    await page.getByText('Biography & relationship evidence', { exact: true }).click();
    await expect(page.getByText('No reviewed biography available. The filing-backed relationship is shown below.')).toBeVisible();
    await page.getByText('Biography & relationship evidence', { exact: true }).click();
    await page.screenshot({ path: 'test-results/controller-desktop.png' });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.locator('.detail-drawer').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await holderToggle.scrollIntoViewIfNeeded();
    await page.screenshot({ path: 'test-results/controller-mobile.png' });
    await page.setViewportSize({ width: 1440, height: 1100 });
  }
  if (d.detail.people.find((p: any) => p.name === holderName)?.ownershipGrid?.length) {
    const grid = page.getByRole('region', { name: 'Stock classes and lock-up periods' });
    await expect(grid).toBeVisible();
    expect(generations).toBe(0);
    await expect(grid.getByRole('columnheader', { name: 'Stock / series' })).toBeVisible();
    const firstPosition = d.detail.people.find((p: any) => p.name === holderName)?.ownershipGrid?.[0];
    if (firstPosition?.attribution?.kind === 'reported_beneficial_owner') {
      await expect(grid.getByText(`SEC-reported beneficial owner · reported holder: ${firstPosition.reportedHolder.name}`, { exact: true }).first()).toBeVisible();
    }
    await grid.getByRole('button', { name: 'Footnotes' }).first().click();
    await expect(grid.locator('.ownership-footnotes')).toBeVisible();
    if (firstPosition?.attribution?.kind === 'reported_beneficial_owner') {
      await expect(grid.getByText('SEC beneficial-owner attribution', { exact: true }).first()).toBeVisible();
    }
    await grid.getByRole('button', { name: 'Footnotes' }).first().click();
    await page.screenshot({ path: 'test-results/ownership-grid-desktop.png' });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(grid).toBeVisible();
    expect(await page.locator('.detail-drawer').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await grid.scrollIntoViewIfNeeded();
    await grid.evaluate(el => { el.scrollLeft = el.scrollWidth; });
    await expect(grid.getByRole('button', { name: 'Footnotes' }).first()).toBeInViewport();
    await page.screenshot({ path: 'test-results/ownership-grid-mobile.png' });
    await grid.evaluate(el => { el.scrollLeft = 0; });
    await page.setViewportSize({ width: 1440, height: 1100 });
  }
  await page.getByRole("button", { name: "Liquidity Analysis", exact: true }).click();
  const analysis = page.getByRole("dialog", { name: `Liquidity Analysis for ${holderName}` });
  await expect(analysis).toBeVisible();
  await expect(analysis.getByText("PRIVATE TO YOUR ACCOUNT")).toBeVisible();
  await expect(analysis.getByRole('heading', { name: /Liquidity timeline/ })).toBeVisible();
  await expect(analysis.getByRole('heading', { name: 'What-if scenario' })).toBeVisible();
  const sidebar = await analysis.locator('.profile-offerings').boundingBox();
  const timeline = await analysis.locator('.profile-timeline-panel').boundingBox();
  const scenario = await analysis.locator('.profile-scenario-panel').boundingBox();
  expect(sidebar!.x).toBeLessThan(timeline!.x);
  expect(timeline!.x).toBeLessThan(scenario!.x);
  expect(Math.abs(timeline!.y - scenario!.y)).toBeLessThan(2);
  await page.screenshot({ path: 'test-results/profile-desktop.png' });
  await analysis.getByText('Ownership grid, assessments & full source versions', { exact: true }).click();
  await expect(analysis.getByText('Retained stake value', { exact: true })).toBeVisible();
  await expect(analysis.getByText('Documented IPO sale proceeds', { exact: true })).toBeVisible();
  await expect(analysis.getByText('Static snapshot · may be stale')).toBeVisible();
  if (liquidityFixture?.positions.length) {
    const p = liquidityFixture.positions[0];
    const grid = analysis.getByRole('region', { name: 'Stock classes and lock-up periods' });
    await expect(grid).toBeVisible();
    await expect(grid.getByText(p.positionBasis === 'post' ? 'Projected after IPO' : 'Before IPO', { exact: true }).first()).toBeVisible();
    const expected = p.quantityKind === 'beneficial_total' && p.components?.status === 'reconciled'
      ? p.components.items.map((c: any) => c.quantity) : [p.reportedTotal ?? p.shares];
    for (const quantity of expected) await expect(grid.getByText(quantity?.toLocaleString() ?? 'Not established', { exact: true }).first()).toBeVisible();
    await grid.getByRole('button', { name: 'Footnotes' }).first().click();
    const notes = grid.locator('.ownership-footnotes');
    await expect(notes).toBeVisible();
    if (p.restrictionTimeline?.length) await expect(notes.getByText(p.restrictionTimeline[0].conditions, { exact: true })).toBeVisible();
    await grid.getByRole('button', { name: 'Footnotes' }).first().click();
    await analysis.getByText('Assessment details & source versions', { exact: true }).click();
    const assessment = analysis.locator('.assessment-detail').first();
    await expect(assessment.getByText(`SEC accession: ${p.filingAccession}`)).toBeVisible();
    const passages = assessment.getByText(`Source passages and footnotes (${p.evidence.length + 1})`, { exact: true });
    await passages.click();
    await expect(assessment.getByText(p.source.excerpt, { exact: true }).first()).toBeVisible();
    await analysis.getByText('Assessment details & source versions', { exact: true }).click();
  } else {
    await expect(analysis.getByText('Holdings review pending · unknown is not zero.')).toBeVisible();
  }
  await analysis.getByLabel('Assumed shares', { exact: true }).fill('1200000');
  await analysis.getByLabel('Assumed price (USD)', { exact: true }).fill('19');
  await expect(analysis.locator('.scenario-output')).toContainText('$22,800,000.00');
  await analysis.getByLabel('Scenario date', { exact: true }).fill('2027-01-01');
  await expect(analysis.getByText(/Reaching a boundary does not establish release/)).toBeVisible();
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
  await analysis.evaluate(el => { el.scrollTop = 0; });
  await page.screenshot({path: "test-results/liquidity-report.png", fullPage: true});
  await analysis.getByRole("button", { name: "Close liquidity analysis" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Liquidity Analysis", exact: true }).click();
  await expect(analysis).toBeVisible();
  const box = await analysis.boundingBox();
  expect(box!.width).toBeLessThanOrEqual(390);
  await page.screenshot({path: "test-results/liquidity-report-mobile.png", fullPage: true});
  expect(await analysis.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  if (!await analysis.locator('.profile-full-evidence').evaluate(el => (el as HTMLDetailsElement).open)) await analysis.getByText('Ownership grid, assessments & full source versions', { exact: true }).click();
  const values = analysis.locator('.wealth-reference > div');
  const left = await values.nth(0).boundingBox();
  const right = await values.nth(1).boundingBox();
  expect(Math.abs(left!.y - right!.y)).toBeLessThan(2);
  await expect(analysis.getByLabel('Assumed shares', { exact: true })).toHaveValue('');
  await expect(analysis.getByLabel('Assumed price (USD)', { exact: true })).toHaveValue('');
  await expect(analysis.getByLabel('Scenario date', { exact: true })).toHaveValue('');
  await analysis.getByRole("button", { name: "Close liquidity analysis" }).click();
  expect(errors).toEqual([]);
});
