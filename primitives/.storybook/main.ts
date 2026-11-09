import type { StorybookConfig } from "@storybook/react-vite";
const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: [
    "@storybook/addon-controls",
    "@storybook/addon-toolbars",
    "@storybook/addon-a11y",
  ],
  framework: "@storybook/react-vite",
};
export default config;
