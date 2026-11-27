"use client";

import { useTranslations } from "next-intl";
import type { PlannedPartOut } from "@/features/topics/api";
import styles from "./TopicSummary.module.css";

interface TopicSummaryProps {
  /** Plan data from the API */
  plan: {
    cost: number;
    available: number;
    parts: PlannedPartOut[];
  } | null;
  /** Whether the plan is loading */
  planLoading: boolean;
  /** Whether there was an error loading the plan */
  planError: boolean;
  /** Whether there are selected topics */
  hasSelection: boolean;
}

export function TopicSummary({
  plan,
  planLoading,
  planError,
  hasSelection,
}: TopicSummaryProps) {
  const t = useTranslations("topics");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");

  const cost = plan?.cost ?? 0;
  const available = plan?.available ?? 0;
  const parts = plan?.parts ?? [];
  const isOverQuota = cost > available;

  const partsCount = parts.length;
  const selectedTopicsCount = parts.reduce((acc) => acc + 1, 0); // Each part = 1 topic selected

  if (planLoading) {
    return (
      <div className={styles.summary} aria-busy="true">
        <div className={styles.row}>
          <span className={styles.label}>{t("selectedLabel")}</span>
          <span className={styles.value}>{tCommon("loading")}</span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>{t("costLabel", { cost: 0 })}</span>
          <span className={styles.value}>{tCommon("loading")}</span>
        </div>
        <div className={styles.quotaRow}>
          <span className={styles.label}>{t("quotaLabel")}</span>
          <span className={styles.value}>{tCommon("loading")}</span>
        </div>
      </div>
    );
  }

  if (planError) {
    return (
      <div className={styles.summary} role="alert">
        <div className={styles.row}>
          <span className={styles.label}>{t("selectedLabel")}</span>
          <span className={styles.value}>
            {hasSelection ? "—" : tCommon("loading")}
          </span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>{t("costLabel", { cost: 0 })}</span>
          <span className={styles.value}>{tCommon("loading")}</span>
        </div>
        <div className={`${styles.quotaRow} ${styles.error}`}>
          <span className={styles.label}>{t("quotaLabel")}</span>
          <span className={styles.value}>{tErrors("unknown_error")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.summary}>
      <div className={styles.row}>
        <span className={styles.value}>
          {t("selectedSummary", {
            topics: selectedTopicsCount,
            parts: partsCount,
          })}
        </span>
      </div>
      <div className={styles.row}>
        <span
          className={`${styles.value} ${styles.cost} ${isOverQuota ? styles.overQuota : ""}`}
        >
          {t("costSummary", { cost })}
        </span>
      </div>
      <div
        className={`${styles.quotaRow} ${isOverQuota ? styles.overQuota : ""}`}
      >
        <span className={styles.label}>{t("quotaLabel")}</span>
        <span className={styles.value}>
          {tCommon("generationsCount", { count: available })}
        </span>
      </div>
      {isOverQuota && (
        <div className={styles.warning} role="alert">
          {t("quotaWarning")}
        </div>
      )}
      {/* Parts preview */}
      {parts.length > 0 && (
        <div className={styles.partsPreview}>
          <div className={styles.partsTitle}>{t("planPreviewTitle")}</div>
          <ul className={styles.partsList}>
            {parts.map((part) => (
              <li key={part.index} className={styles.partItem}>
                <span className={styles.partIndex}>#{part.index}</span>
                <span className={styles.partTitle}>{part.title}</span>
                <span className={styles.partTokens}>{part.tokens}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
