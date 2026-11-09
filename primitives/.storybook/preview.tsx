import type { Preview } from "@storybook/react";
import { useLayoutEffect, type ReactNode } from "react";
import "../src/tokens/tokens.css";
import "./preview.css";

function Theme({
  theme,
  locale,
  children,
}: {
  theme: string;
  locale: string;
  children: ReactNode;
}) {
  useLayoutEffect(() => {
    const previous = document.documentElement.getAttribute("data-theme");
    document.documentElement.setAttribute("data-theme", theme);
    return () => {
      if (previous === null)
        document.documentElement.removeAttribute("data-theme");
      else document.documentElement.setAttribute("data-theme", previous);
    };
  }, [theme]);
  return (
    <div
      className="design-preview primitive-preview"
      lang={locale}
      data-theme={theme}
    >
      {children}
    </div>
  );
}

const preview: Preview = {
  globalTypes: {
    locale: {
      description: "Widget locale",
      toolbar: { icon: "globe", items: ["en", "ru"] },
    },
    theme: {
      description: "Color theme",
      toolbar: { icon: "paintbrush", items: ["light", "dark"] },
    },
  },
  initialGlobals: { locale: "en", theme: "light" },
  decorators: [
    (Story, context) => {
      const locale = context.globals.locale === "ru" ? "ru" : "en";
      const theme = context.globals.theme === "dark" ? "dark" : "light";
      const args = context.title.startsWith("Primitives/")
        ? { ...context.args, locale }
        : context.args;
      return (
        <Theme theme={theme} locale={locale}>
          <Story args={args} />
        </Theme>
      );
    },
  ],
};
export default preview;
