import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: ["fixtures/**/tests/**/*.spec.mjs", "tests/visual/**/*.spec.mjs"],
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "docs/test-output/playwright-report" }]],
  snapshotPathTemplate: "tests/visual/baselines/{arg}{ext}",
  expect: { toHaveScreenshot: { maxDiffPixels: 150 } },
  use: {
    trace: "off",
    video: "off",
    locale: "en-US",
    timezoneId: "UTC",
    colorScheme: "light",
    reducedMotion: "reduce",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
