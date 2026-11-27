"use client";

import { useFormatter } from "next-intl";
import { useTranslations } from "next-intl";
import { useQuota } from "@/entities/user";
import { ApiError } from "@/shared/api/errors";
import styles from "./QuotaCard.module.css";

export function QuotaCard() {
  const t = useTranslations("materials");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");
  const format = useFormatter();
  const quota = useQuota();

  if (quota.isPending) {
    return (
      <div className={styles.card} aria-busy="true">
        <div className={styles.header}>
          <span className={styles.title}>{t("quotaTitle")}</span>
          <span className={styles.value} aria-hidden="true">
            —
          </span>
        </div>
        <div
          className={styles.progressWrapper}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={0}
          aria-label={t("quotaProgressLabel", { used: 0, total: 0 })}
        >
          <div className={styles.progressBar} style={{ width: "0%" }} />
        </div>
        <p className={styles.period}>{tCommon("loading")}</p>
      </div>
    );
  }

  if (quota.isError) {
    const message =
      quota.error instanceof ApiError
        ? tErrors(quota.error.code)
        : tErrors("unknown_error");

    return (
      <div className={styles.card} role="status">
        <div className={styles.header}>
          <span className={styles.title}>{t("quotaTitle")}</span>
          <span className={styles.value} aria-hidden="true">
            !
          </span>
        </div>
        <p className={styles.errorMessage}>{message}</p>
        <button
          type="button"
          className={styles.retry}
          onClick={() => void quota.refetch()}
        >
          {tCommon("retry")}
        </button>
      </div>
    );
  }

  const { available, monthly_limit: total, period_end } = quota.data;
  const used = total - available;
  const percent =
    total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0;
  const exhausted = available <= 0;

  // period_end is exclusive bound (first day of next period), so show period_end - 1 day
  const periodEndDate = new Date(period_end);
  periodEndDate.setDate(periodEndDate.getDate() - 1);
  const formattedPeriodEnd = format.dateTime(periodEndDate, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });

  return (
    <div className={styles.card} aria-live="polite">
      <div className={styles.header}>
        <span className={styles.title}>{t("quotaTitle")}</span>
        <span
          className={`${styles.value} ${exhausted ? styles.exhausted : ""}`}
          aria-hidden="true"
        >
          {available}
        </span>
      </div>
      <div
        className={styles.progressWrapper}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={used}
        aria-label={t("quotaProgressLabel", { used, total })}
      >
        <div
          className={`${styles.progressBar} ${exhausted ? styles.exhausted : ""}`}
          style={{ width: `${String(percent)}%` }}
        />
      </div>
      <p className={styles.meta}>
        <span>{t("quotaProgressLabel", { used, total })}</span>
        <time dateTime={period_end}>
          {t("quotaPeriodEnd", { date: formattedPeriodEnd })}
        </time>
      </p>
    </div>
  );
}
