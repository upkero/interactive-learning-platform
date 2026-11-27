/** Exact set of imports supplied by the widget host runtime. */
export const ALLOWED_WIDGET_IMPORTS = [
  "react",
  "react/jsx-runtime",
  "d3",
  "@grasp/primitives/ui",
] as const;

export type InitMessage = {
  type: "grasp:init";
  code: string;
  params: Record<string, unknown>;
  mode: "watch" | "steps" | "predict";
  labels: Record<string, string>;
  theme: "light" | "dark";
  locale: string;
};

export type WidgetToHost =
  | { type: "grasp:ready" }
  | { type: "grasp:resize"; height: number }
  | { type: "grasp:state"; value: unknown }
  | { type: "grasp:error"; message: string };
