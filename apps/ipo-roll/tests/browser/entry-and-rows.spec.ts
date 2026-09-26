import { test, expect } from '@playwright/test';

test('IPO rows open from cells; bookmarks, keyboard and column controls remain independent', async ({ page }) => {
  await page.goto('/#activity');
  const row = page.locator('.research-table .offering-row').first();
  await expect(row).toBeVisible();
  const company = row.locator('.company-cell');
  await row.locator('td').nth(3).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(company).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await row.getByRole('button', { name: /^Save / }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(row.getByRole('button', { name: /^Unsave / })).toBeVisible();
  await page.getByRole('button', { name: 'Columns', exact: true }).click();
  await page.getByRole('button', { name: 'Move Ticker left' }).click();
  await expect(page.locator('.research-table th').first()).toContainText('Ticker');
  await row.locator('td').first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: /Saved \/ Watchlist/ }).click();
  await page.locator('.offering-row td').first().click({ position: { x: 3, y: 3 } });
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await page.locator('.mini-table .offering-row').first().locator('td').nth(2).click();
  await expect(page.getByRole('dialog')).toBeVisible();
});

test('login visualization is local, pausable, responsive and honors reduced motion', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  let researchRequests = 0;
  page.on('request', req => { if (/\/api\/(overview|offerings|people|saved)/.test(req.url())) researchRequests++; });
  await page.route('**/api/config', route => route.fulfill({ json: {
    demo: false, configured: true, url: 'https://auth.example.test', key: 'publishable',
  } }));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome to IPO Roll' })).toBeVisible();
  await expect(page.locator('.login-flow')).toBeVisible();
  await expect(page.locator('video, iframe')).toHaveCount(0);
  await expect(page.locator('.flow-packet')).toHaveCount(6);
  await page.getByRole('button', { name: 'Pause visualization' }).click();
  expect(await page.locator('.flow-packet').first().evaluate(el => getComputedStyle(el).animationPlayState)).toBe('paused');
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: 'test-results/login-flow-desktop.png', fullPage: true });
  await page.getByRole('button', { name: 'Play visualization' }).click();
  expect(await page.locator('.flow-packet').first().evaluate(el => getComputedStyle(el).animationPlayState)).toBe('running');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({ path: 'test-results/login-flow-mobile.png', fullPage: true, animations: 'disabled' });
  await page.getByLabel('Email address').fill('reviewer@example.invalid');
  await page.getByLabel('Password', { exact: true }).fill('not-a-real-credential');
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeEnabled();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.getByRole('button', { name: 'Animation off for reduced motion' })).toBeDisabled();
  expect(await page.locator('.flow-packet').first().evaluate(el => getComputedStyle(el).animationName)).toBe('none');
  expect(researchRequests).toBe(0);
  expect(errors).toEqual([]);
});
