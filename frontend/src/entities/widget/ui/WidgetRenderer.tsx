'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';
import { useWidgetReport } from '../model/useWidgetReport';
import type { Widget, ConfigWidget, CodeWidget, FallbackWidget } from '../model/types';
import styles from './WidgetRenderer.module.css';

interface WidgetRendererProps {
  /** The widget to render */
  widget: Widget;
  /** Widget ID (used for reporting) */
  widgetId: string;
  /** Part ID for reporting context */
  partId?: string | null;
  /** Callback when widget reports height change */
  onHeightChange?: (height: number) => void;
  /** Whether to show the report button */
  showReportButton?: boolean;
  /** Callback when report is submitted successfully */
  onReportSubmitted?: () => void;
}

/**
 * Renders a widget based on its type:
 * - ConfigWidget: rendered in an isolated iframe pointing to widget-host with config mode
 * - CodeWidget: rendered in an isolated iframe pointing to widget-host with compiled JS
 * - PendingWidget: shows loading spinner
 * - FallbackWidget: shows fallback content (text or image placeholder)
 */
export function WidgetRenderer({
  widget,
  widgetId,
  partId,
  onHeightChange,
  showReportButton = true,
  onReportSubmitted,
}: WidgetRendererProps) {
  const t = useTranslations('viewer');
  const [iframeHeight, setIframeHeight] = useState<number>(300);
  const [loadError, setLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const heightCheckIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Handle postMessage from iframe for auto-height
  const handleMessage = useCallback((event: MessageEvent) => {
    // Only accept messages from our widget host origin
    // In production, this should be the actual widget-host domain
    const allowedOrigins = [
      'http://localhost:3001', // widget-host dev server
      'https://widget-host.grasp.app', // production
      window.location.origin, // same origin for testing
    ];

    if (!allowedOrigins.includes(event.origin)) {
      return;
    }

    // Type-safe access to event.data
    const data = event.data as { type?: string; height?: number } | null;
    if (!data?.type) return;

    if (data.type === 'widget:height' && typeof data.height === 'number') {
      const newHeight = Math.max(200, Math.min(data.height, 2000));
      setIframeHeight(newHeight);
      onHeightChange?.(newHeight);
    } else if (data.type === 'widget:ready') {
      setIsLoading(false);
    } else if (data.type === 'widget:error') {
      setIsLoading(false);
      setLoadError(true);
    }
  }, [onHeightChange]);

  useEffect(() => {
    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
      if (heightCheckIntervalRef.current) {
        clearInterval(heightCheckIntervalRef.current);
      }
    };
  }, [handleMessage]);

  // Reset state when widget changes
  useEffect(() => {
    setIsLoading(true);
    setLoadError(false);
    setIframeHeight(300);
  }, [widgetId, widget]);

  // Periodic height check as fallback
  useEffect(() => {
    if (!iframeRef.current) return;

    heightCheckIntervalRef.current = setInterval(() => {
      try {
        // Try to get height from iframe content (same-origin only)
        const iframe = iframeRef.current;
        if (iframe && iframe.contentDocument) {
          const height = iframe.contentDocument.body.scrollHeight;
          if (height > 200 && height !== iframeHeight) {
            setIframeHeight(Math.min(height, 2000));
            onHeightChange?.(height);
          }
        }
      } catch {
        // Cross-origin, ignore
      }
    }, 1000);

    return () => {
      if (heightCheckIntervalRef.current) {
        clearInterval(heightCheckIntervalRef.current);
      }
    };
  }, [iframeHeight, onHeightChange]);

  const handleRetry = useCallback(() => {
    setIsLoading(true);
    setLoadError(false);
    if (iframeRef.current) {
      iframeRef.current.src = iframeRef.current.src; // Reload iframe
    }
  }, []);

  // Pending widget
  if ('status' in widget && widget.status === 'pending') {
    return (
      <div className={styles.widgetPending} role="status" aria-label={t('widgetPending')}>
        <div className={styles.widgetSpinner} aria-hidden="true" />
        <p>{widget.title || t('widgetPending')}</p>
      </div>
    );
  }

  // Fallback widget
  if ('status' in widget && widget.status === 'fallback') {
    const fallback = (widget as FallbackWidget).fallback;
    return (
      <div className={styles.widgetFallback} role="note">
        {fallback.type === 'text' ? (
          <p>{fallback.text}</p>
        ) : (
          <p>{t('widgetFallback')}</p>
        )}
      </div>
    );
  }

  // Ready widgets (ConfigWidget or CodeWidget)
  const isConfig = 'kind' in widget && widget.kind === 'config';
  const isCode = 'kind' in widget && widget.kind === 'code';

  // Build widget host URL
  // In production, this would be a separate widget-host service
  // For now, we use a local route that serves the widget host
  const widgetHostBase = process.env.NEXT_PUBLIC_WIDGET_HOST_URL || 'http://localhost:3001';
  const widgetUrl = new URL(`/widget/${widgetId}`, widgetHostBase);
  widgetUrl.searchParams.set('mode', isConfig ? 'config' : 'code');
  if (isConfig) {
    const configWidget = widget satisfies ConfigWidget;
    widgetUrl.searchParams.set('primitive_id', configWidget.primitive_id);
    widgetUrl.searchParams.set('widget_mode', configWidget.mode);
    // Pass params as JSON
    widgetUrl.searchParams.set('params', JSON.stringify(configWidget.params));
  } else if (isCode) {
    const codeWidget = widget satisfies CodeWidget;
    if (codeWidget.compiled_js) {
      widgetUrl.searchParams.set('compiled_js', btoa(codeWidget.compiled_js));
    }
    if (codeWidget.labels) {
      widgetUrl.searchParams.set('labels', JSON.stringify(codeWidget.labels));
    }
  }
  widgetUrl.searchParams.set('title', widget.title);

  return (
    <div className={styles.widgetContainer} role="region" aria-label={widget.title}>
      {showReportButton && (
        <WidgetReportButton
          widgetId={widgetId}
          partId={partId}
          onReportSubmitted={onReportSubmitted}
        />
      )}

      {isLoading && !loadError && (
        <div className={styles.widgetLoading} role="status" aria-label={t('widgetPending')}>
          <div className={styles.widgetSpinner} aria-hidden="true" />
          <p>{t('widgetPending')}</p>
        </div>
      )}

      {loadError && (
        <div className={styles.widgetError} role="alert">
          <svg className={styles.widgetErrorIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <h3 className={styles.widgetErrorTitle}>{t('widgetLoadError')}</h3>
          <p className={styles.widgetErrorMessage}>{t('widgetLoadErrorHint')}</p>
          <button type="button" className={styles.widgetRetryButton} onClick={handleRetry}>
            {t('retry')}
          </button>
        </div>
      )}

      {!isLoading && !loadError && (
        <iframe
          ref={iframeRef}
          className={styles.widgetIframe}
          src={widgetUrl.toString()}
          title={widget.title}
          height={iframeHeight}
          width="100%"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
          allow="clipboard-read; clipboard-write"
          loading="lazy"
          onLoad={() => {
            // Initial load - still wait for widget:ready message
            setTimeout(() => { setIsLoading(false); }, 500);
          }}
        />
      )}
    </div>
  );
}

interface WidgetReportButtonProps {
  widgetId: string;
  partId?: string | null;
  onReportSubmitted?: () => void;
}

function WidgetReportButton({ widgetId, partId, onReportSubmitted }: WidgetReportButtonProps) {
  const t = useTranslations('viewer');
  const [showModal, setShowModal] = useState(false);

  const handleOpenModal = () => {
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
  };

  return (
    <>
      <button
        type="button"
        className={styles.widgetReportButton}
        onClick={handleOpenModal}
        aria-label={t('reportWidgetButton')}
        aria-haspopup="dialog"
      >
        <svg className={styles.widgetReportIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <span>{t('reportWidgetButton')}</span>
      </button>

      {showModal && (
        <WidgetReportModal
          widgetId={widgetId}
          partId={partId}
          onClose={handleCloseModal}
          onSubmitted={onReportSubmitted}
        />
      )}
    </>
  );
}

interface WidgetReportModalProps {
  widgetId: string;
  partId?: string | null;
  onClose: () => void;
  onSubmitted?: () => void;
}

/**
 * Modal for reporting widget issues.
 * Matches the API: POST /api/v1/widgets/{widget_id}/reports
 * Body: { reason: "wrong" | "broken" | "ugly" | "other", comment?: string, part_id?: string }
 */
function WidgetReportModal({
  widgetId,
  partId,
  onClose,
  onSubmitted,
}: WidgetReportModalProps) {
  const t = useTranslations('report');
  const tErrors = useTranslations('errors');
  const tCommon = useTranslations('common');

  const [reason, setReason] = useState<'wrong' | 'broken' | 'ugly' | 'other'>('wrong');
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const { mutateAsync: reportWidget } = useWidgetReport();

  const reasons: { value: 'wrong' | 'broken' | 'ugly' | 'other'; label: string }[] = [
    { value: 'wrong', label: t('reasonInaccurate') },
    { value: 'broken', label: t('reasonBroken') },
    { value: 'ugly', label: t('reasonUnhelpful') },
    { value: 'other', label: t('reasonOther') },
  ];

  const handleSubmit = (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmitError(null);
    setIsSubmitting(true);

    void (async () => {
      try {
        await reportWidget({
          widgetId,
          body: {
            reason,
            comment: comment.trim() || undefined,
            part_id: partId || undefined,
          },
        });
        setSubmitSuccess(true);
        onSubmitted?.();
        // Close after brief success display
        setTimeout(() => {
          onClose();
          setSubmitSuccess(false);
          setComment('');
          setReason('wrong');
        }, 1500);
      } catch (error) {
        if (error instanceof Error) {
          // Try to extract error code from error message or use generic
          const errorCode = error.message.includes('widget_not_found') ? 'widget_not_found'
            : error.message.includes('queue_unavailable') ? 'queue_unavailable'
            : 'unknown_error';
          setSubmitError(tErrors(errorCode));
        } else {
          setSubmitError(tErrors('unknown_error'));
        }
      } finally {
        setIsSubmitting(false);
      }
    })();
  };

  return (
    <div className={styles.modalOverlay} role="dialog" aria-modal="true" aria-labelledby="report-modal-title">
      <div className={styles.modal}>
        <header className={styles.modalHeader}>
          <h2 id="report-modal-title" className={styles.modalTitle}>{t('title')}</h2>
          <button
            type="button"
            className={styles.modalClose}
            onClick={() => { onClose(); }}
            aria-label={tCommon('close')}
            disabled={isSubmitting}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        {submitSuccess ? (
          <div className={styles.modalSuccess} role="status">
            <svg className={styles.successIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            <p>{t('submittedToast')}</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.modalForm}>
            <fieldset className={styles.reasonFieldset}>
              <legend className={styles.reasonLegend}>{t('reasonLabel')}</legend>
              <div className={styles.reasonOptions}>
                {reasons.map((r) => (
                  <label key={r.value} className={styles.reasonOption}>
                    <input
                      type="radio"
                      name="reason"
                      value={r.value}
                      checked={reason === r.value}
                      onChange={() => { setReason(r.value); }}
                      className={styles.reasonRadio}
                      disabled={isSubmitting}
                    />
                    <span className={styles.reasonLabel}>{r.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className={styles.commentField}>
              <label htmlFor="report-comment" className={styles.commentLabel}>
                {t('commentLabel')}
              </label>
              <textarea
                id="report-comment"
                className={styles.commentTextarea}
                value={comment}
                onChange={(e) => { setComment(e.target.value); }}
                placeholder={t('commentPlaceholder')}
                rows={3}
                disabled={isSubmitting}
                maxLength={1000}
              />
              <p className={styles.commentHint}>{comment.length}/1000</p>
            </div>

            {submitError && (
              <div className={styles.submitError} role="alert">
                {submitError}
              </div>
            )}

            <div className={styles.modalActions}>
              <button
                type="button"
                className={`${styles.modalAction} ${styles.modalActionSecondary}`}
                onClick={() => { onClose(); }}
                disabled={isSubmitting}
              >
                {tCommon('cancel')}
              </button>
              <button
                type="submit"
                className={`${styles.modalAction} ${styles.modalActionPrimary}`}
                disabled={isSubmitting}
              >
                {isSubmitting ? tCommon('loading') : t('submitButton')}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}