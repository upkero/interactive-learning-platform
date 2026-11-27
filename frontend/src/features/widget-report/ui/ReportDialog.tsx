"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { useReportWidget, type WidgetReportReason } from "../api";
import { Dialog } from "@/shared/ui";
import { isApiError } from "@/shared/api/errors";
import styles from "./ReportDialog.module.css";

interface ReportDialogProps {
  widgetId: string;
  partId?: string | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

const REASON_OPTIONS: { value: WidgetReportReason; labelKey: string }[] = [
  { value: "broken", labelKey: "reasonBroken" },
  { value: "wrong", labelKey: "reasonInaccurate" },
  { value: "ugly", labelKey: "reasonUnhelpful" },
  { value: "other", labelKey: "reasonOther" },
];

export function ReportDialog({
  widgetId,
  partId,
  isOpen,
  onClose,
  onSuccess,
}: ReportDialogProps) {
  const t = useTranslations("report");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");

  const [reason, setReason] = useState<WidgetReportReason>("broken");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reportMutation = useReportWidget();

  const handleClose = useCallback(() => {
    setReason("broken");
    setComment("");
    setError(null);
    onClose();
  }, [onClose]);

  const getErrorMessage = useCallback(
    (err: unknown): string => {
      if (isApiError(err)) {
        return tErrors(err.code);
      }
      if (err instanceof TypeError && err.message.includes("fetch")) {
        return tErrors("network_error");
      }
      if (err instanceof Error) {
        return tErrors("unknown_error");
      }
      return tErrors("unknown_error");
    },
    [tErrors]
  );

  const handleSubmit = useCallback(
    async (e: React.SubmitEvent<HTMLFormElement>) => {
      e.preventDefault();
      setError(null);

      try {
        await reportMutation.mutateAsync({
          widgetId,
          body: {
            reason,
            part_id: partId ?? null,
            comment: comment.trim() || null,
          },
        });
        onSuccess?.();
        handleClose();
      } catch (err) {
        setError(getErrorMessage(err));
      }
    },
    [
      widgetId,
      partId,
      reason,
      comment,
      reportMutation,
      onSuccess,
      handleClose,
      getErrorMessage,
    ]
  );

  if (!isOpen) return null;

  return (
    <Dialog isOpen={isOpen} onClose={handleClose} title={t("title")} size="md">
      <form
        onSubmit={(e) => {
          void handleSubmit(e);
        }}
        className={styles.form}
      >
        <fieldset className={styles.reasonFieldset}>
          <legend className={styles.legend}>{t("reasonLabel")}</legend>
          <div
            className={styles.radioGroup}
            role="radiogroup"
            aria-labelledby="report-reason-label"
          >
            {REASON_OPTIONS.map((option) => (
              <label key={option.value} className={styles.radioLabel}>
                <input
                  type="radio"
                  name="reason"
                  value={option.value}
                  checked={reason === option.value}
                  onChange={() => {
                    setReason(option.value);
                  }}
                  className={styles.radioInput}
                />
                <span className={styles.radioText}>{t(option.labelKey)}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className={styles.commentGroup}>
          <label htmlFor="report-comment" className={styles.label}>
            {t("commentLabel")}
          </label>
          <textarea
            id="report-comment"
            className={styles.commentInput}
            value={comment}
            onChange={(e) => {
              setComment(e.target.value);
            }}
            placeholder={t("commentPlaceholder")}
            rows={4}
            disabled={reportMutation.isPending}
          />
        </div>

        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}

        <div className={styles.actions}>
          <button
            type="button"
            className={`${styles.actionButton} ${styles.secondary}`}
            onClick={handleClose}
            disabled={reportMutation.isPending}
          >
            {tCommon("cancel")}
          </button>
          <button
            type="submit"
            className={`${styles.actionButton} ${styles.primary}`}
            disabled={reportMutation.isPending}
          >
            {reportMutation.isPending ? tCommon("loading") : t("submitButton")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
