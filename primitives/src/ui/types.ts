import type { Labels } from "../core/labels";

/** Props supplied by the host to generated code widgets. */
export interface WidgetProps<P> {
  params: P;
  mode: "watch" | "steps" | "predict";
  labels: Labels;
}
