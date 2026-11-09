import type { Preview } from "@storybook/react";
import "../src/tokens/tokens.css";
import "./preview.css";

const preview: Preview = {
  globalTypes: { theme: { description: "Color theme", toolbar: { icon: "paintbrush", items: ["light", "dark"] } } },
  initialGlobals: { theme: "light" },
  decorators: [(Story, context) => <div className="design-preview" data-theme={context.globals.theme === "dark" ? "dark" : "light"}><Story /></div>],
};
export default preview;
