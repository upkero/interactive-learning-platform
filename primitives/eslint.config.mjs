import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["storybook-static/**", "dist/**", "test-results/**", "playwright-report/**"] },
  ...tseslint.configs.recommended,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
);
