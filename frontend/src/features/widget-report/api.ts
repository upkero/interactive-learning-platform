"use client";

import { useMutation } from "@tanstack/react-query";
import { apiClient, unwrap } from "@/shared/api";
import type { components } from "@/shared/api/schema";

export type WidgetReportReason =
  components["schemas"]["WidgetReportRequest"]["reason"];

export interface ReportWidgetParams {
  widgetId: string;
  body: {
    reason: WidgetReportReason;
    part_id?: string | null;
    comment?: string | null;
  };
}

export function useReportWidget() {
  return useMutation({
    mutationFn: async ({ widgetId, body }: ReportWidgetParams) => {
      return unwrap(
        apiClient.POST("/api/v1/widgets/{widget_id}/reports", {
          params: { path: { widget_id: widgetId } },
          body,
        })
      );
    },
  });
}
