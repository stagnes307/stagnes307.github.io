import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.STUDY_E2E_PORT || 4173);
const origin = process.env.STUDY_E2E_ORIGIN || `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  timeout: 30_000,
  expect: {
    timeout: 8_000,
  },
  reporter: [
    ["list"],
    [
      "html",
      {
        outputFolder: "../../.cache/question-bank-playwright-report",
        open: "never",
      },
    ],
  ],
  outputDir: "../../.cache/question-bank-playwright-results",
  use: {
    baseURL: origin,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command: `python -m http.server ${port} --bind 127.0.0.1 --directory ../..`,
    url: `${origin}/study/courses/big-data-analysis-engineer-written/questions/`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    stdout: "pipe",
    stderr: "pipe",
  },
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium-mobile",
      use: { ...devices["Pixel 7"] },
    },
  ],
});
