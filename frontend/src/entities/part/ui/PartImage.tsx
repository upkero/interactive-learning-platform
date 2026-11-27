"use client";

import { useTranslations } from "next-intl";
import type { ImageOut } from "@/entities/part";
import styles from "./PartImage.module.css";

interface PartImageProps {
  image: ImageOut;
}

export function PartImage({ image }: PartImageProps) {
  const t = useTranslations("viewer");

  if (!image.url) {
    return (
      <figure
        className={styles.figure}
        role="img"
        aria-label={t("imageMissing")}
      >
        <div className={styles.placeholder} />
        {image.caption && (
          <figcaption className={styles.caption}>{image.caption}</figcaption>
        )}
      </figure>
    );
  }

  return (
    <figure
      className={styles.figure}
      role="img"
      aria-label={image.caption || t("image")}
    >
      <img
        src={image.url}
        alt={image.caption || t("image")}
        className={styles.image}
        loading="lazy"
      />
      {image.caption && (
        <figcaption className={styles.caption}>{image.caption}</figcaption>
      )}
    </figure>
  );
}
