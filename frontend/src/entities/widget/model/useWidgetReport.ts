'use client';

import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/shared/api/client';
import type { WidgetReportRequest, WidgetReportResponse } from '../model/types';

/** Query key for widget reports (not used for caching, but for invalidation patterns) */
export const WIDGET_REPORT_MUTATION_KEY = ['widget', 'report'] as const;

/**
 * Hook for reporting a widget issue.
 * Uses the POST /api/v1/widgets/{widget_id}/reports endpoint.
 */
export function useWidgetReport() {
  // const queryClient = useQueryClient(); // reserved for future cache invalidation

  return useMutation<WidgetReportResponse, Error, { widgetId: string; body: WidgetReportRequest }>({
    mutationKey: WIDGET_REPORT_MUTATION_KEY,
    mutationFn: async ({ widgetId, body }) => {
      const { data, response } = await apiClient.POST('/api/v1/widgets/{widget_id}/reports', {
        params: { path: { widget_id: widgetId } },
        body,
      });
      if (!response.ok || !data) {
        throw new Error('Failed to report widget');
      }
      return data;
    },
    onSuccess: () => {
      // Optionally invalidate related queries if needed
      // queryClient.invalidateQueries({ queryKey: ['widget', widgetId] });
    },
  });
}