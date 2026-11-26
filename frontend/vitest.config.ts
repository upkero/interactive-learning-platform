import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "next/navigation": path.resolve(
        __dirname,
        "./vitest.mocks/next-navigation.ts"
      ),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    deps: {
      inline: ["next-intl"],
    },
  },
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
  },
});
