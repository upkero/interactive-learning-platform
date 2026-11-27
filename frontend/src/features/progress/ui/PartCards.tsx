"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/shared/i18n/navigation";
import styles from "./PartCards.module.css";

interface PartCardProps {
  part: {
    id: string;
    index: number;
    title: string;
    status:
      | "queued"
      | "main_pass"
      | "resolving"
      | "assembling"
      | "published"
      | "failed";
    errorCode?: string;
  };
}

export function PartCards({ parts }: { parts: PartCardProps["part"][] }) {
  const t = useTranslations("progress");
  const tErrors = useTranslations("errors");

  const statusConfig = {
    queued: { label: t("partStatus.queued"), className: styles.statusQueued },
    main_pass: {
      label: t("partStatus.mainPass"),
      className: styles.statusGenerating,
    },
    resolving: {
      label: t("partStatus.resolving"),
      className: styles.statusGenerating,
    },
    assembling: {
      label: t("partStatus.assembling"),
      className: styles.statusGenerating,
    },
    published: {
      label: t("partStatus.published"),
      className: styles.statusPublished,
    },
    failed: { label: t("partStatus.failed"), className: styles.statusFailed },
  } as const;

  const sortedParts = [...parts].sort((a, b) => a.index - b.index);

  if (sortedParts.length === 0) {
    return (
      <p className={styles.emptyParts} role="status">
        {t("waitingForParts")}
      </p>
    );
  }

  return (
    <div className={styles.partsList} role="list">
      {sortedParts.map((part) => (
        <article
          key={part.id}
          className={`${styles.partCard} ${styles[part.status]}`}
          role="listitem"
        >
          <header className={styles.partHeader}>
            <h3 className={styles.partTitle}>{part.title}</h3>
            <span
              className={`${styles.partStatus} ${statusConfig[part.status].className}`}
            >
              {statusConfig[part.status].label}
            </span>
          </header>

          {part.status === "main_pass" ||
          part.status === "resolving" ||
          part.status === "assembling" ? (
            <div
              className={styles.partProgress}
              role="progressbar"
              aria-valuenow={0}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={statusConfig[part.status].label}
            >
              <div className={styles.partProgressFill} />
            </div>
          ) : null}

          {part.status === "published" && (
            <div className={styles.partActions}>
              <Link href={`/parts/${part.id}`} className={styles.openButton}>
                {t("openMaterialButton")}
              </Link>
            </div>
          )}

          {part.status === "failed" && part.errorCode && (
            <div className={styles.partError} role="alert">
              <p className={styles.partErrorText}>{tErrors(part.errorCode)}</p>
              <p className={styles.partErrorHint}>{t("partFailedHint")}</p>
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
