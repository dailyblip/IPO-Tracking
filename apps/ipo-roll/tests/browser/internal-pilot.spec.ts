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
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
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
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".match-card")).toHaveCount(1);
  await expect(
    page.locator("mark").filter({ hasText: "University of Michigan" }).first(),
  ).toBeVisible();
  await expect(page.getByText("Brent Jewell").first()).toBeVisible();
  await page.screenshot({
    path: process.env.IPO_ROLL_PILOT_SCREENSHOT || "test-results/pilot.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Open Accelevation Holdings Corp." })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText("Michael Rubiera").first()).toBeVisible();
  expect(errors).toEqual([]);
});
