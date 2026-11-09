import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
const en: Record<string, string> = JSON.parse(
  readFileSync("src/i18n/en.json", "utf8")
);
const ru: Record<string, string> = JSON.parse(
  readFileSync("src/i18n/ru.json", "utf8")
);

const examples = [
  { name: "add-two", params: { left: 3, right: 2 } },
  { name: "add-zero", params: { left: 4, right: 0 } },
  { name: "add-one", params: { left: 2, right: 1 } },
];
const stories: Record<string, string> = {
  "add-two": "add-two",
  "add-zero": "add-zero",
  "add-one": "add-one",
};

for (const example of examples)
  for (const mode of ["watch", "steps", "predict"] as const) {
    for (const locale of ["en", "ru"] as const)
      for (const theme of ["light", "dark"] as const) {
        test(`${example.name} / ${mode} / ${locale} / ${theme}`, async ({
          page,
        }) => {
          const errors: string[] = [];
          page.on("pageerror", (error) => errors.push(error.message));
          await page.setViewportSize({ width: 320, height: 800 });
          await page.goto(
            `/iframe.html?id=primitives-three-frame--${stories[example.name]}&viewMode=story&args=mode:${mode}&globals=locale:${locale};theme:${theme}`
          );
          const labels = locale === "en" ? en : ru;
          await expect(page.getByRole("tablist")).toHaveCount(0);
          await expect(page.locator(".primitive-preview")).toHaveAttribute(
            "data-theme",
            theme
          );
          if (mode === "watch") {
            await expect(
              page.getByText(locale === "en" ? "Step 3 of 3" : "Шаг 3 из 3", {
                exact: true,
              })
            ).toBeVisible({ timeout: 5000 });
          } else
            await page
              .getByRole("button", { name: labels["common.next"], exact: true })
              .click();
          if (mode === "predict") {
            await expect(
              page.getByRole("button", {
                name: labels["common.next"],
                exact: true,
              })
            ).toBeDisabled();
            const question = page.locator("fieldset");
            await expect(question).toBeVisible();
            const panelBox = await question.boundingBox();
            const nextBox = await page
              .getByRole("button", { name: labels["common.next"], exact: true })
              .boundingBox();
            expect(panelBox!.y + panelBox!.height).toBeLessThanOrEqual(
              nextBox!.y
            );
            await page
              .getByRole("button", {
                name: labels[
                  example.params.right > 0 ? "common.yes" : "common.no"
                ],
                exact: true,
              })
              .click();
            await expect(
              page.getByText(labels["common.correct"], { exact: true })
            ).toBeVisible();
          }
          if (mode !== "watch")
            await page
              .getByRole("button", { name: labels["common.next"], exact: true })
              .click();
          await expect(
            page.getByRole("button", {
              name: labels["common.next"],
              exact: true,
            })
          ).toBeDisabled();
          await expect(
            page.getByText(
              `${example.params.left} + ${example.params.right} = ${example.params.left + example.params.right}`,
              { exact: true }
            )
          ).toBeVisible();
          expect(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= window.innerWidth
            )
          ).toBe(true);
          expect(errors).toEqual([]);
        });
      }
  }

test("invalid params show an error without rendering the primitive", async ({
  page,
}) => {
  await page.goto(
    "/iframe.html?id=primitives-three-frame--invalid-params&viewMode=story"
  );
  await expect(page.getByRole("alert")).toContainText(
    "Invalid primitive parameters"
  );
  await expect(page.getByRole("tablist")).toHaveCount(0);
});

test("predict moves keyboard focus to the first answer", async ({ page }) => {
  await page.goto(
    "/iframe.html?id=primitives-three-frame--add-two&viewMode=story&args=mode:predict"
  );
  const next = page.getByRole("button", { name: "Next", exact: true });
  await next.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "Yes", exact: true })
  ).toBeFocused();
});

test("reduced motion does not autoplay watch", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(
    "/iframe.html?id=primitives-three-frame--add-two&viewMode=story&args=mode:watch"
  );
  await expect(
    page.getByRole("button", { name: "Play", exact: true })
  ).toBeVisible();
  await page.waitForTimeout(1400);
  await expect(page.getByText("Step 1 of 3", { exact: true })).toBeVisible();
});

test("manager toolbar switches locale and theme; Actions receives primitive events", async ({
  page,
}) => {
  await page.goto("/?path=/story/primitives-three-frame--add-two");
  const canvas = page.frameLocator("#storybook-preview-iframe");
  await expect(
    canvas.getByRole("button", { name: "Next", exact: true })
  ).toBeVisible();
  await page.getByRole("button", { name: "Widget locale" }).click();
  await page.getByText("ru", { exact: true }).click();
  await expect(
    canvas.getByRole("button", { name: "Далее", exact: true })
  ).toBeVisible();
  await page.getByRole("button", { name: "Color theme" }).click();
  await page.getByText("dark", { exact: true }).click();
  await expect(canvas.locator(".primitive-preview")).toHaveAttribute(
    "data-theme",
    "dark"
  );
  await page.getByRole("tab", { name: /Actions/ }).click();
  await canvas.getByRole("button", { name: "Далее", exact: true }).click();
  await expect(
    page.getByText("primitive:event", { exact: false }).first()
  ).toBeVisible();
});

test("every indexed story renders without a runtime error", async ({
  page,
  request,
}) => {
  const response = await request.get("/index.json");
  const index = await response.json();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const story of Object.values(index.entries) as {
    id: string;
    type: string;
  }[]) {
    if (story.type !== "story") continue;
    await page.goto(`/iframe.html?id=${story.id}&viewMode=story`);
    await expect(page.locator("#storybook-root")).not.toBeEmpty();
    await expect(page.locator(".sb-errordisplay")).not.toBeVisible();
  }
  expect(errors).toEqual([]);
});
