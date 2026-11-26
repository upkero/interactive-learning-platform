"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/shared/i18n/navigation-client";
import {
  useEventStream,
  type SseEventMessage,
} from "@/shared/lib/sse/useEventStream";
import { useDocumentStatusGuard } from "@/entities/document";
import { useDocument } from "@/entities/document";
import { ActionLink } from "@/shared/ui";
import styles from "./ParsingCard.module.css";

interface ParsingEventData {
  stage: string;
  progress?: number;
  message?: string;
  document_id: string;
  status: "parsing" | "parsed" | "generating" | "done" | "failed";
  error_code?: string;
}

export function ParsingCard({ documentId }: { documentId: string }) {
  const t = useTranslations("upload");
  const tErrors = useTranslations("errors");
  const tCommon = useTranslations("common");
  const tProgress = useTranslations("progress");

  const router = useRouter();

  const [parsingProgress, setParsingProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [hasRedirected, setHasRedirected] = useState(false);

  // Centralized status guard - upload step allows 'parsing' status
  const {
    status,
    isLoading,
    error,
    hasRedirected: guardRedirected,
  } = useDocumentStatusGuard({
    documentId,
    currentStep: "upload",
    onRedirect: () => {
      setHasRedirected(true);
    },
  });

  // Get full document for error_code
  const { data: document } = useDocument(documentId);

  const handleEvent = (message: SseEventMessage<ParsingEventData>) => {
    if (hasRedirected || guardRedirected) return;

    const data = message.data;
    if (data.progress !== undefined) {
      setParsingProgress(data.progress);
    }
    if (data.stage) {
      setCurrentStage(data.stage);
    }
    // Handle real API statuses
    if (data.status === "parsed") {
      setHasRedirected(true);
      router.replace(`/documents/${documentId}/topics`);
    } else if (data.status === "failed") {
      setErrorCode(data.error_code || "parse_failed");
    } else if (data.status === "generating") {
      setHasRedirected(true);
      router.replace(`/documents/${documentId}/progress`);
    }
    // "done" status is handled by the guard
  };

  const sseUrl = `/api/v1/documents/${documentId}/events`;

  const { status: sseStatus } = useEventStream<ParsingEventData>({
    url: sseUrl,
    enabled: !hasRedirected && !errorCode && !guardRedirected,
    // Use default event types from useEventStream
    onEvent: handleEvent,
  });

  // Also poll document status as fallback
  useEffect(() => {
    if (hasRedirected || errorCode || guardRedirected || !status) return;

    if (status === "parsed") {
      setHasRedirected(true);
      router.replace(`/documents/${documentId}/topics`);
    } else if (status === "failed") {
      setErrorCode(document?.error_code || "parse_failed");
    } else if (status === "generating") {
      setHasRedirected(true);
      router.replace(`/documents/${documentId}/progress`);
    } else if (status === "done") {
      // The guard will handle redirect to first published part or materials
    }
  }, [
    status,
    hasRedirected,
    errorCode,
    guardRedirected,
    router,
    documentId,
    document?.error_code,
  ]);

  const handleReplaceFile = () => {
    router.replace("/upload");
  };

  if (isLoading) {
    return (
      <div className={styles.card} role="status" aria-live="polite">
        <div className={styles.skeleton}>
          <div className={styles.skeletonTitle} />
          <div className={styles.skeletonBar} />
          <div className={styles.skeletonText} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.card} role="alert">
        <div className={styles.errorState}>
          <h2 className={styles.errorTitle}>{t("parsingFailed")}</h2>
          <p className={styles.errorMessage}>{t("documentLoadFailed")}</p>
          <div className={styles.errorActions}>
            <ActionLink
              href="/materials"
              variant="secondary"
              className={styles.actionButton}
            >
              {tCommon("back")}
            </ActionLink>
          </div>
        </div>
      </div>
    );
  }

  if (errorCode) {
    return (
      <div className={styles.card} role="alert">
        <div className={styles.errorState}>
          <h2 className={styles.errorTitle}>{t("parsingFailed")}</h2>
          <p className={styles.errorMessage}>
            {tErrors(errorCode as keyof typeof tErrors)}
          </p>
          <div className={styles.errorActions}>
            <button
              type="button"
              className={`${styles.actionButton} ${styles.primary}`}
              onClick={handleReplaceFile}
            >
              {t("replaceFileButton")}
            </button>
            <ActionLink
              href="/materials"
              variant="secondary"
              className={styles.actionButton}
            >
              {tCommon("back")}
            </ActionLink>
          </div>
        </div>
      </div>
    );
  }

  if (guardRedirected) {
    return null;
  }

  return (
    <div className={styles.card} role="status" aria-live="polite">
      <h2 className={styles.title}>{t("parsingTitle")}</h2>

      <div className={styles.progressWrapper}>
        <div
          className={styles.progressBar}
          role="progressbar"
          aria-valuenow={parsingProgress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={t("parsingTitle")}
        >
          <div
            className={styles.progressFill}
            style={{ width: `${String(parsingProgress)}%` }}
          />
        </div>
        <span className={styles.progressText}>{parsingProgress}%</span>
      </div>

      {currentStage && <p className={styles.stageText}>{currentStage}</p>}

      {sseStatus === "reconnecting" && (
        <div className={styles.reconnectBanner} role="status">
          {tProgress("connectionLost")}
        </div>
      )}
    </div>
  );
}
