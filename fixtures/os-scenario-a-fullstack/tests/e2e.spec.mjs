import { test, expect } from "@playwright/test";

const PORT = process.env.SCENARIO_A_PORT || 3847;
const BASE = `http://127.0.0.1:${PORT}`;

test.describe("Scenario A full-stack", () => {
  test("health + items + validation + error state", async ({ page }) => {
    const res = await page.request.get(`${BASE}/api/health`);
    expect(res.ok()).toBeTruthy();
    await page.goto(BASE);
    await expect(page.getByTestId("app-root")).toBeVisible();
    await expect(page.getByTestId("items-list")).toContainText("OS validation seed");
    await page.getByTestId("title-input").fill("<bad>");
    await page.getByTestId("submit-btn").click();
    await expect(page.getByTestId("form-error")).toBeVisible();
    await page.getByTestId("error-demo-btn").click();
    await expect(page.getByTestId("list-error")).toContainText("Simulated");
  });
});
