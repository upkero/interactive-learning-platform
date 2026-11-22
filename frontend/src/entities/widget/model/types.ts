import type { components } from '@/shared/api/schema';

/** Union of all widget types from the API */
export type Widget = ConfigWidget | CodeWidget | PendingWidget | FallbackWidget;

/** Widget with kind: "config" */
export type ConfigWidget = components['schemas']['ConfigWidget'];

/** Widget with kind: "code" */
export type CodeWidget = components['schemas']['CodeWidget'];

/** Widget with status: "pending" */
export type PendingWidget = components['schemas']['PendingWidget'];

/** Widget with status: "fallback" */
export type FallbackWidget = components['schemas']['PendingWidget'] & { status: 'fallback' };

/** Type guard for ConfigWidget */
export function isConfigWidget(widget: Widget): widget is ConfigWidget {
  return 'kind' in widget && widget.kind === 'config';
}

/** Type guard for CodeWidget */
export function isCodeWidget(widget: Widget): widget is CodeWidget {
  return 'kind' in widget && widget.kind === 'code';
}

/** Type guard for pending/fallback widgets */
export function isPendingOrFallbackWidget(widget: Widget): widget is PendingWidget | FallbackWidget {
  return 'status' in widget && (widget.status === 'pending' || widget.status === 'fallback');
}

/** Widget report reason enum from API */
export type WidgetReportReason = components['schemas']['WidgetReportRequest']['reason'];

/** Widget report request payload */
export type WidgetReportRequest = components['schemas']['WidgetReportRequest'];

/** Widget report response */
export type WidgetReportResponse = components['schemas']['WidgetReportResponse'];