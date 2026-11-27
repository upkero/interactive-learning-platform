"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/shared/i18n/navigation-client";
import { useDocumentStatusGuard } from "@/entities/document";
import { ActionLink } from "@/shared/ui";
import styles from "./ParsingCard.module.css";

export function ParsingCard({ documentId }: { documentId: string }) {
  const t = useTranslations("upload");
  const tErrors = useTranslations("errors");
  const tCommon = useTranslations("common");
  const router = useRouter();

  const { document, status, isLoading, error, hasRedirected } =
    useDocumentStatusGuard({ documentId, currentStep: "upload" });

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

  const errorCode = status === "failed" ? document?.error_code : null;
  if (error || errorCode) {
    const message = errorCode
      ? errorCode === "too_many_pages"
        ? tErrors(errorCode)
        : t(`documentErrors.${errorCode}`)
      : t("documentLoadFailed");

    return (
      <div className={styles.card} role="alert">
        <div className={styles.errorState}>
          <h2 className={styles.errorTitle}>{t("parsingFailed")}</h2>
          <p className={styles.errorMessage}>{message}</p>
          <div className={styles.errorActions}>
            {errorCode && (
              <button
                type="button"
                className={`${styles.actionButton} ${styles.primary}`}
                onClick={() => router.replace("/upload")}
              >
                {t("replaceFileButton")}
              </button>
            )}
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

  if (hasRedirected) return null;

  const title = t(status === "uploaded" ? "parsingPending" : "parsingTitle");
  return (
    <div className={styles.card} role="status" aria-live="polite">
      <h2 className={styles.title}>{title}</h2>
      <div className={styles.skeleton}>
        <div
          className={styles.skeletonBar}
          role="progressbar"
          aria-label={title}
        />
      </div>
    </div>
  );
}
