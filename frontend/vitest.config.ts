import path from "node:path";
import { configDefaults, defineConfig } from "vitest/config";

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
    exclude: [...configDefaults.exclude, "tests/**/*.test.mjs"],
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
