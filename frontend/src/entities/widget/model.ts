import type { components } from "@/shared/api/schema";

export type ConfigWidget = components["schemas"]["ConfigWidget"];
export type CodeWidget = components["schemas"]["CodeWidget"];
export type PendingWidget = components["schemas"]["PendingWidget"];
export type ImageFallback = components["schemas"]["ImageFallback"];
export type TextFallback = components["schemas"]["TextFallback"];

export type Widget = ConfigWidget | CodeWidget | PendingWidget;

export type WidgetFallback = ImageFallback | TextFallback;

export interface WidgetSlot {
  key: string;
  title: string;
  status: "pending" | "fallback" | "ready";
  fallback?: WidgetFallback;
  config?: ConfigWidget;
  code?: CodeWidget;
}
