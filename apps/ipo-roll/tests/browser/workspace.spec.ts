import { mkdirSync } from "node:fs";
import { join } from "node:path";
const screenshotDir =
  process.env.IPO_ROLL_SCREENSHOT_DIR || "test-results/screenshots";
mkdirSync(screenshotDir, { recursive: true });
import { test, expect } from "@playwright/test";
test("overview, evidence search, company accordion and watchlist work", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByText("SAMPLE WORKSPACE")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "The IPO landscape, in focus." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "People Search", exact: true })
    .click();
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("Morgan Vale").first()).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Evidence trail" }),
  ).toBeVisible();
  await page.getByLabel("Relationship filter").selectOption("Director");
  await expect(page.getByText("Avery Chen").first()).toBeVisible();
  await expect(page.locator(".match-card")).toHaveCount(1);
  await page.getByRole("button", { name: "Open Kestrel Systems" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .getByRole("button", { name: "Save Kestrel Systems", exact: true })
    .click();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /Saved \/ Watchlist/ }).click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.reload();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Unsave Kestrel Systems", exact: true })
    .click();
  await expect(page.getByText("No saved offerings")).toBeVisible();
  expect(errors).toEqual([]);
});
test("size filters, column keyboard controls, mobile layout and empty search", async ({
  page,
}) => {
  await page.goto("/#activity");
  await page.getByLabel("Offering size filter").selectOption("1000000000");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("button", { name: "Columns", exact: true }).click();
  await page.getByRole("button", { name: "Move Ticker left" }).click();
  await expect(page.locator("th").first()).toContainText("Ticker");
  await page.getByRole("button", { name: "Reset order" }).click();
  await page
    .getByRole("button", { name: "People Search", exact: true })
    .click();
  await page.getByLabel("Search biographies").fill("no supported match xyz");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("No supported matches found")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "Methodology", exact: true }).click();
  await expect(page.getByText("Evidence is the foundation.")).toBeVisible();
});
test("capture approved visual direction", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Offerings to explore")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: join(screenshotDir, "IPO_Roll_Build_Overview.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "People Search", exact: true })
    .click();
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Evidence trail" }),
  ).toBeVisible();
  await page.screenshot({
    path: join(screenshotDir, "IPO_Roll_Build_People_Search.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
  await page.screenshot({
    path: join(screenshotDir, "IPO_Roll_Build_Mobile.png"),
    fullPage: true,
    animations: "disabled",
  });
});

test("signed-in member without research access sees account state", async ({
  page,
}) => {
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: {
        demo: false,
        configured: true,
        url: "https://auth.example.test",
        key: "publishable",
      },
    }),
  );
  await page.route("https://auth.example.test/**", (route) => {
    if (route.request().url().includes("/token"))
      return route.fulfill({
        json: {
          access_token: "test-session",
          refresh_token: "test-refresh",
          expires_in: 3600,
          token_type: "bearer",
          user: {
            id: "10000000-0000-4000-8000-000000000001",
            email: "member@example.invalid",
            aud: "authenticated",
          },
        },
      });
    return route.fulfill({ status: 204 });
  });
  await page.route("**/api/account", (route) =>
    route.fulfill({
      json: {
        email: "member@example.invalid",
        researchAccess: false,
        billing: { status: "not_configured", interval: "month" },
      },
    }),
  );
  let researchRequests = 0;
  page.on("request", (req) => {
    if (/\/api\/(overview|offerings|people|saved)/.test(req.url()))
      researchRequests++;
  });
  await page.goto("/");
  await page.getByLabel("Email address").fill("member@example.invalid");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your account is ready" }),
  ).toBeVisible();
  await expect(
    page.getByText("Checkout is not open. You have not been charged."),
  ).toBeVisible();
  expect(researchRequests).toBe(0);
});
