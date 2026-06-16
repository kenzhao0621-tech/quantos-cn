import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, "..", "..");
const PAGE = path.join(ROOT, "fixtures/visual-qa/index.html");

const VIEWPORTS = [
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1280x800", width: 1280, height: 800 },
  { name: "768x1024", width: 768, height: 1024 },
  { name: "390x844", width: 390, height: 844 },
  { name: "360x800", width: 360, height: 800 },
];

test.describe("Visual baselines", () => {
  for (const vp of VIEWPORTS) {
    test(`baseline ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto(`file://${PAGE}`);
      await page.waitForLoadState("domcontentloaded");
      await page.evaluate(() => document.fonts?.ready);
      await expect(page).toHaveScreenshot(`visual-qa-${vp.name}.png`, {
        animations: "disabled",
        fullPage: true,
      });
    });
  }
});
