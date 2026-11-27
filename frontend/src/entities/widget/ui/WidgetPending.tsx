"use client";

import { useTranslations } from "next-intl";
import styles from "./WidgetPending.module.css";

export function WidgetPending({ title }: { title: string }) {
  const t = useTranslations("viewer");

  return (
    <figure
      className={styles.figure}
      role="status"
      aria-label={t("widgetPending")}
    >
      <div className={styles.spinner} aria-hidden="true" />
      <figcaption className={styles.caption}>
        <span className={styles.title}>{title}</span>
        <p>{t("widgetPending")}</p>
      </figcaption>
    </figure>
  );
}
