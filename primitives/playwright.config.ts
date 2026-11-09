import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/storybook",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:6007", browserName: "chromium" },
  webServer: { command: "node --experimental-strip-types scripts/serve-storybook.ts", url: "http://127.0.0.1:6007", reuseExistingServer: false },
});
