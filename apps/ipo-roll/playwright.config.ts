import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests/browser",
  use: {
    baseURL: "http://127.0.0.1:4100",
    viewport: { width: 1440, height: 1100 },
    headless: true,
    launchOptions: process.env.CHROMIUM_PATH
      ? {
          executablePath: process.env.CHROMIUM_PATH,
          args: ["--no-sandbox", "--disable-dev-shm-usage"],
        }
      : {},
  },
  workers: 1,
  webServer: {
    command: "IPO_ROLL_DEMO=1 PORT=4100 node --import tsx server/index.ts",
    url: "http://127.0.0.1:4100/api/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
