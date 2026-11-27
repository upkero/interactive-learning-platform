"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useDocumentStatusGuard } from "@/entities/document";
import { useProgressState } from "@/features/progress/api";
import { PartCards } from "./PartCards";
import { StageLog } from "./StageLog";
import { KeyTerms } from "./KeyTerms";
import { PageShell } from "@/shared/ui/page-shell/PageShell";
import { Surface } from "@/shared/ui/surface/Surface";
import { ActionLink } from "@/shared/ui/action-link/ActionLink";
import styles from "./ProgressFeature.module.css";

export function ProgressFeature({ documentId }: { documentId: string }) {
  const t = useTranslations("progress");
  const tCommon = useTranslations("common");
  const tUpload = useTranslations("upload");

  const {
    isLoading,
    error,
    hasRedirected: guardRedirected,
  } = useDocumentStatusGuard({
    documentId,
    currentStep: "progress",
  });

  const { state, sseStatus, documentQuery } = useProgressState(documentId);

  // Track part durations for ETA calculation
  const partDurations = useRef<number[]>([]);

  // Calculate ETA based on completed part durations
  const eta = useMemo(() => {
    const publishedParts = state.parts.filter((p) => p.status === "published");
    const remainingParts = state.parts.filter(
      (p) => p.status !== "published" && p.status !== "failed"
    );

    if (publishedParts.length === 0 || remainingParts.length === 0) {
      return null;
    }

    if (partDurations.current.length === 0) {
      return null;
    }

    const avgDuration =
      partDurations.current.reduce((a, b) => a + b, 0) /
      partDurations.current.length;
    return Math.ceil(avgDuration * remainingParts.length);
  }, [state.parts]);

  // Track connection lost state
  const [showConnectionLost, setShowConnectionLost] = useState(false);

  useEffect(() => {
    if (state.connectionLost) {
      setShowConnectionLost(true);
    } else if (sseStatus === "open") {
      setShowConnectionLost(false);
    }
  }, [state.connectionLost, sseStatus]);

  // Handle retry when connection lost
  const handleRetry = useCallback(() => {
    // Force a refetch of the document and restart SSE
    void documentQuery.refetch();
    setShowConnectionLost(false);
  }, [documentQuery]);

  // Loading state
  if (isLoading) {
    return (
      <PageShell
        title={t("title")}
        description={t("etaRemaining", { seconds: 0 })}
      >
        <ProgressSkeleton tCommon={tCommon} />
      </PageShell>
    );
  }

  // Error state from document guard
  if (error) {
    return (
      <PageShell title={t("title")}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <h2 className={styles.errorTitle}>{tUpload("parsingFailed")}</h2>
            <p className={styles.errorMessage}>{t("documentLoadFailed")}</p>
            <div className={styles.errorActions}>
              <button
                type="button"
                className={`${styles.actionButton} ${styles.primary}`}
                onClick={handleRetry}
              >
                {t("retryButton")}
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
        </Surface>
      </PageShell>
    );
  }

  if (guardRedirected) {
    return null;
  }

  // Fatal error from SSE
  if (state.errorCode) {
    return (
      <PageShell title={t("title")}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <h2 className={styles.errorTitle}>{t("generationError")}</h2>
            <p className={styles.errorMessage}>
              {t("fatalErrorMessage", { code: state.errorCode })}
            </p>
            <div className={styles.errorActions}>
              <button
                type="button"
                className={`${styles.actionButton} ${styles.primary}`}
                onClick={handleRetry}
              >
                {t("retryButton")}
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
        </Surface>
      </PageShell>
    );
  }

  return (
    <PageShell
      title={t("title")}
      description={
        eta !== null ? t("etaRemaining", { seconds: eta }) : t("canClosePage")
      }
    >
      {showConnectionLost && (
        <div className={styles.connectionLostBanner} role="alert">
          <p>{t("connectionLost")}</p>
          <button
            type="button"
            className={styles.retryButton}
            onClick={handleRetry}
          >
            {t("retryButton")}
          </button>
        </div>
      )}

      {sseStatus === "reconnecting" && !showConnectionLost && (
        <div className={styles.reconnectBanner} role="status">
          {t("reconnecting")}
        </div>
      )}

      <Surface title={t("stageLogTitle")}>
        <StageLog entries={state.stageLog} />
      </Surface>

      <Surface title={t("partsTitle")}>
        <PartCards parts={state.parts} />
      </Surface>

      <Surface title={t("keyTermsTitle")} muted>
        <KeyTerms terms={state.keyTerms} />
      </Surface>

      <div className={styles.actions}>
        <ActionLink href="/materials" variant="secondary">
          {t("backToMaterials")}
        </ActionLink>
      </div>
    </PageShell>
  );
}

interface ProgressSkeletonProps {
  tCommon: ReturnType<typeof useTranslations>;
}

function ProgressSkeleton({ tCommon }: ProgressSkeletonProps) {
  return (
    <div
      className={styles.skeleton}
      role="status"
      aria-label={tCommon("loading")}
    >
      <Surface>
        <div className={styles.skeletonStageLog}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={styles.skeletonStageItem} />
          ))}
        </div>
      </Surface>
      <Surface>
        <div className={styles.skeletonParts}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={styles.skeletonPartItem} />
          ))}
        </div>
      </Surface>
      <Surface>
        <div className={styles.skeletonKeyTerms} />
      </Surface>
    </div>
  );
}
