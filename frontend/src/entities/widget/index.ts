export {
  type Widget,
  type ConfigWidget,
  type CodeWidget,
  type PendingWidget,
  type FallbackWidget,
  isConfigWidget,
  isCodeWidget,
  isPendingOrFallbackWidget,
  type WidgetReportReason,
  type WidgetReportRequest,
  type WidgetReportResponse,
} from './model/types';

export { useWidgetReport } from './model/useWidgetReport';
export { WidgetRenderer } from './ui/WidgetRenderer';