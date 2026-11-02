import type { Preview } from "@storybook/react";

import en from "../src/i18n/en.json";
import ru from "../src/i18n/ru.json";
import "../src/tokens/tokens.css";

const preview: Preview = {
  globalTypes: {
    locale: { description: "Widget locale", toolbar: { icon: "globe", items: ["en", "ru"] } },
    theme: { description: "Color theme", toolbar: { icon: "paintbrush", items: ["light", "dark"] } },
  },
  initialGlobals: { locale: "en", theme: "light" },
  decorators: [
    (Story, context) => {
      const locale = context.globals.locale === "ru" ? "ru" : "en";
      const labels = locale === "ru" ? ru : en;
      return <div data-theme={context.globals.theme === "dark" ? "dark" : "light"} style={{ background: "var(--g-color-bg)", color: "var(--g-color-text)", minHeight: "100vh", padding: "24px" }}><Story args={{ ...context.args, labels }} /></div>;
    },
  ],
};

export default preview;
