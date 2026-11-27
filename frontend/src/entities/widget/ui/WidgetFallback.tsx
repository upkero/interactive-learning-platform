"use client";

import { useTranslations } from "next-intl";
import { PartImage } from "@/entities/part";
import type { ImageFallback, TextFallback } from "@/entities/widget";
import type { ImageOut } from "@/entities/part";
import styles from "./WidgetFallback.module.css";

interface WidgetFallbackProps {
  fallback: ImageFallback | TextFallback;
  images: Record<string, ImageOut>;
  title: string;
}

export function WidgetFallback({
  fallback,
  images,
  title,
}: WidgetFallbackProps) {
  const t = useTranslations("viewer");

  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  if (fallback.type === "image" && images[fallback.image_id]) {
    const image = images[fallback.image_id];
    return (
      <figure className={styles.figure} role="img" aria-label={title}>
        <PartImage image={image} />
        <figcaption className={styles.caption}>
          <span className={styles.title}>{title}</span>
          <p>{t("widgetFallback")}</p>
        </figcaption>
      </figure>
    );
  }

  if (fallback.type === "text") {
    return (
      <figure className={styles.figure} role="note" aria-label={title}>
        <div className={styles.textFallback}>
          <p>{fallback.text}</p>
        </div>
        <figcaption className={styles.caption}>
          <span className={styles.title}>{title}</span>
          <p>{t("widgetFallback")}</p>
        </figcaption>
      </figure>
    );
  }

  return (
    <figure className={styles.figure} role="note" aria-label={title}>
      <figcaption className={styles.caption}>
        <span className={styles.title}>{title}</span>
        <p>{t("widgetFallback")}</p>
      </figcaption>
    </figure>
  );
}
