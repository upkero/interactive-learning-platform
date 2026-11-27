"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ReportDialog } from "./ReportDialog";
import styles from "./ReportButton.module.css";

interface ReportButtonProps {
  widgetId: string;
  partId?: string | null;
}

export function ReportButton({ widgetId, partId }: ReportButtonProps) {
  const t = useTranslations("viewer");
  const tReport = useTranslations("report");

  const [isOpen, setIsOpen] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const handleOpen = useCallback(() => {
    setIsOpen(true);
    setIsSubmitted(false);
  }, []);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    buttonRef.current?.focus();
  }, []);

  const handleSuccess = useCallback(() => {
    setIsSubmitted(true);
    setIsOpen(false);
  }, []);

  const handleReportClick = useCallback(() => {
    if (isSubmitted) return;
    handleOpen();
  }, [isSubmitted, handleOpen]);

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className={`${styles.button} ${isSubmitted ? styles.submitted : ""}`}
        onClick={handleReportClick}
        disabled={isSubmitted}
        aria-label={
          isSubmitted ? tReport("submittedToast") : t("reportWidgetButton")
        }
      >
        {isSubmitted ? (
          <>
            <svg
              className={styles.checkIcon}
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <span>{tReport("submittedToast")}</span>
          </>
        ) : (
          t("reportWidgetButton")
        )}
      </button>
      <ReportDialog
        widgetId={widgetId}
        partId={partId}
        isOpen={isOpen}
        onClose={handleClose}
        onSuccess={handleSuccess}
      />
    </>
  );
}
