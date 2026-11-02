import type { Preview } from "@storybook/react";
import "../src/tokens/tokens.css";
import "./preview.css";

const preview: Preview = {
  globalTypes: {
    locale: { description: "Widget locale", toolbar: { icon: "globe", items: ["en", "ru"] } },
    theme: { description: "Color theme", toolbar: { icon: "paintbrush", items: ["light", "dark"] } },
  },
  initialGlobals: { locale: "en", theme: "light" },
  decorators: [(Story, context) => <div className="design-preview primitive-preview" lang={context.globals.locale === "ru" ? "ru" : "en"} data-theme={context.globals.theme === "dark" ? "dark" : "light"}><Story args={{ ...context.args, locale: context.globals.locale === "ru" ? "ru" : "en" }} /></div>],
};
export default preview;
