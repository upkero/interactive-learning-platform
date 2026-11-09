import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

for (const theme of ["light", "dark"] as const) {
  test(`all UI stories pass axe in ${theme} theme`, async ({ page, request }) => {
    const index = await (await request.get("/index.json")).json();
    const stories = (Object.values(index.entries) as { id: string; type: string }[])
      .filter((entry) => entry.type === "story" && entry.id.startsWith("ui-"));
    expect(stories.length).toBeGreaterThanOrEqual(7);
    const screenshots = join(process.cwd(), "test-results", "screenshots");
    mkdirSync(screenshots, { recursive: true });
    for (const story of stories) {
      await page.goto(`/iframe.html?id=${story.id}&viewMode=story&globals=theme:${theme}`);
      await expect(page.locator(".design-preview")).toHaveAttribute("data-theme", theme);
      await expect(page.locator("#storybook-root")).not.toBeEmpty();
      const results = await new AxeBuilder({ page }).include("#storybook-root")
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      expect(results.violations, `${story.id} ${theme}: ${JSON.stringify(results.violations)}`).toEqual([]);
      await page.screenshot({ path: join(screenshots, `${story.id}-${theme}.png`) });
    }
  });
  test(`nested ${theme} theme respects reduced motion`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(`/iframe.html?id=ui-toggle--default&viewMode=story&globals=theme:${theme}`);
    const preview = page.locator(".design-preview");
    await expect(preview).toHaveAttribute("data-theme", theme);
    expect(await preview.evaluate((el) => getComputedStyle(el).getPropertyValue("--g-duration-fast").trim())).toBe("0ms");
  });
}

test("native range supports arrows, PageUp and precise decimals", async ({ page }) => {
  await page.goto("/iframe.html?id=ui-slider--default&viewMode=story&args=min:0;max:1;step:0.1;value:0.2");
  const slider = page.getByRole("slider", { name: "Speed" });
  await slider.focus();
  await page.keyboard.press("ArrowRight");
  await expect(slider).toHaveValue("0.3");
  await expect(slider).toBeFocused();
  await page.keyboard.press("PageUp");
  await expect.poll(async () => Number(await slider.inputValue())).toBeGreaterThan(0.3);
});

test("focus moves to Back when Next becomes disabled", async ({ page }) => {
  await page.goto("/iframe.html?id=ui-stepcontrols--default&viewMode=story&args=currentStep:3;totalSteps:4");
  const next = page.getByRole("button", { name: "Next" });
  await next.focus();
  await page.keyboard.press("Enter");
  await expect(next).toBeDisabled();
  await expect(page.getByRole("button", { name: "Previous" })).toBeFocused();
});

test("Storybook toolbar changes the component theme", async ({ page }) => {
  await page.goto("/?path=/story/ui-button--ghost");
  const canvas = page.frameLocator("#storybook-preview-iframe");
  await expect(canvas.getByRole("button", { name: "Continue" })).toBeVisible();
  await page.getByRole("button", { name: "Color theme" }).click();
  await page.getByText("dark", { exact: true }).click();
  await expect(canvas.locator(".design-preview")).toHaveAttribute("data-theme", "dark");
});

test("Storybook Controls update the rendered component", async ({ page }) => {
  await page.goto("/?path=/story/ui-slider--default");
  const canvas = page.frameLocator("#storybook-preview-iframe");
  await expect(canvas.getByRole("slider", { name: "Speed" })).toBeVisible();
  await page.getByRole("tab", { name: /Controls/ }).click();
  await page.locator("#control-label").fill("Playback speed");
  await expect(canvas.getByRole("slider", { name: "Playback speed" })).toBeVisible();
});

test("long mode labels wrap within a 320px viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto("/iframe.html?id=ui-modetabs--long-labels&viewMode=story");
  await expect(page.getByRole("tab", { name: "Предсказать результат" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
