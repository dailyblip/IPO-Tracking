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
  await expect(page.getByText(holderName).first()).toBeVisible();
  const holderToggle = page.locator('.person-toggle').filter({ hasText: holderName });
  if (await holderToggle.getAttribute('aria-expanded') !== 'true') await holderToggle.click();
  if (d.detail.people.find((p: any) => p.name === holderName)?.ownershipGrid?.length) {
    const grid = page.getByRole('region', { name: 'Stock classes and lock-up periods' });
    await expect(grid).toBeVisible();
    expect(generations).toBe(0);
    await expect(grid.getByRole('columnheader', { name: 'Stock / series' })).toBeVisible();
    await grid.getByRole('button', { name: 'Footnotes' }).first().click();
    await expect(grid.locator('.ownership-footnotes')).toBeVisible();
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
  if (liquidityFixture) {
    const p = liquidityFixture.positions[0];
    await expect(analysis.getByText(p.positionBasis === 'post' ? "Projected post-offering position" : "Pre-offering position", { exact: true })).toBeVisible();
    const quantityLabel = p.quantityKind === 'beneficial_total'
      ? `${p.reportedTotal.toLocaleString()} reported beneficial interests (includes awards)`
      : `${p.shares.toLocaleString()} disclosed shares`;
    await expect(analysis.getByText(`${quantityLabel} · Filing date ${p.filingDate || p.holdingsDate}`, { exact: true })).toBeVisible();
    if (p.quantityKind === 'beneficial_total') {
      const components = analysis.locator('.holding-components');
      await expect(components.getByRole('heading', { name: 'What the reported total includes' })).toBeVisible();
      await expect(components.getByText(/parts of the total, not additional positions/)).toBeVisible();
      await expect(components.locator('summary')).toHaveCount(p.components.items.length);
      const labels: Record<string, string> = { common_share: 'Common shares', rsu: 'RSU underlying shares', option: 'Option underlying shares', warrant: 'Warrant underlying shares' };
      for (const c of p.components.items) {
        const card = components.locator('.source-box').filter({ has: page.getByText(`${labels[c.instrument]}: ${c.quantity.toLocaleString()}`, { exact: true }) });
        await expect(card).toBeVisible();
        await expect(card.getByText(c.description, { exact: true })).toBeVisible();
        await card.getByText('Component evidence', { exact: true }).click();
        await expect(card.getByText(c.source.excerpt, { exact: true })).toBeVisible();
        await card.getByText('Component evidence', { exact: true }).click();
      }
      await expect(analysis.getByText(`${p.reportedTotal.toLocaleString()} disclosed shares`, { exact: false })).toHaveCount(0);
    }
    await expect(analysis.getByText(`Holdings as of: ${p.holdingsAsOf || 'Not established in this snapshot'}. This is not confirmation of current holdings.`, { exact: true })).toBeVisible();
    const passages = `Source passages and footnotes (${p.evidence.length + 1})`;
    const sourceDetails = analysis.locator('details').filter({ has: page.getByText(passages, { exact: true }) });
    await analysis.getByText(passages, { exact: true }).click();
    await expect(sourceDetails.getByText(p.evidence.at(-1).excerpt, { exact: true })).toBeVisible();
    await expect(sourceDetails.getByText(/Source blocks? \d+/).first()).toBeVisible();
    await analysis.getByText(passages, { exact: true }).click();
    if (p.restrictionTimeline?.length) {
      const t = p.restrictionTimeline[0];
      const timeline = analysis.locator('.restriction-timeline');
      await expect(timeline.getByRole('heading', { name: 'Conditional restriction timeline' })).toBeVisible();
      await expect(timeline.getByText(`Scheduled boundary: ${t.boundaryDate}`, { exact: true })).toBeVisible();
      await expect(timeline.getByText(`${t.trigger}: ${t.triggerDate} + ${t.dayCount} calendar days.`, { exact: true })).toBeVisible();
      await expect(timeline.getByText(/not a confirmed release or first tradable date/)).toBeVisible();
      await timeline.locator('summary').click();
      for (const source of t.evidence) await expect(timeline.getByText(source.excerpt, { exact: true })).toBeVisible();
      await timeline.locator('summary').click();
      await expect(analysis.getByText('Insufficient evidence', { exact: true }).last()).toBeVisible();
    } else {
      await expect(analysis.getByText(/Lock-up start: Not confirmed/)).toBeVisible();
    }
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
  await analysis.evaluate(el => { el.scrollTop = 0; });
  await page.screenshot({path: "test-results/liquidity-report.png", fullPage: true});
  await analysis.getByRole("button", { name: "Close liquidity analysis" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Liquidity Analysis", exact: true }).click();
  await expect(analysis).toBeVisible();
  const box = await analysis.boundingBox();
  expect(box!.width).toBeLessThanOrEqual(390);
  await page.screenshot({path: "test-results/liquidity-report-mobile.png", fullPage: true});
  if (liquidityFixture?.positions[0]?.restrictionTimeline?.length) {
    await analysis.getByRole('heading', { name: 'Conditional restriction timeline' }).scrollIntoViewIfNeeded();
    expect(await analysis.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.screenshot({path: 'test-results/liquidity-timeline-mobile.png'});
  }
  if (liquidityFixture?.positions[0]?.quantityKind === 'beneficial_total') {
    await analysis.getByRole('heading', { name: 'What the reported total includes' }).scrollIntoViewIfNeeded();
    expect(await analysis.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.screenshot({path: 'test-results/liquidity-components-mobile.png'});
  }
  await analysis.getByRole("button", { name: "Close liquidity analysis" }).click();
  expect(errors).toEqual([]);
});
