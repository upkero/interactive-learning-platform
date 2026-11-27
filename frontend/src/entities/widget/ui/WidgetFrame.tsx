"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import type { CodeWidget } from "@/entities/widget";
import styles from "./WidgetFrame.module.css";

interface WidgetFrameProps {
  widget: CodeWidget;
  title: string;
}

export function WidgetFrame({ widget, title }: WidgetFrameProps) {
  const t = useTranslations("viewer");
  const locale = useLocale();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isReady, setIsReady] = useState(false);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const handleMessage = (event: MessageEvent) => {
      const data = event.data as Record<string, unknown> | undefined;
      if (data?.type === "grasp:widget:ready") {
        setIsReady(true);
        iframe.contentWindow?.postMessage(
          {
            type: "grasp:widget:init",
            code: widget.compiled_js,
            params: widget.labels || {},
            mode: "watch",
            labels: widget.labels || {},
            locale,
          },
          "*"
        );
      } else if (data?.type === "grasp:widget:error") {
        setHasError(true);
      }
    };

    window.addEventListener("message", handleMessage);
    iframe.onload = () => {
      if (!isReady) {
        setTimeout(() => {
          setHasError(true);
        }, 10_000);
      }
    };

    return () => {
      window.removeEventListener("message", handleMessage);
    };
  }, [widget.compiled_js, widget.labels, locale, isReady]);

  if (hasError || !widget.compiled_js) {
    return (
      <figure
        className={styles.figure}
        role="alert"
        aria-label={t("widgetError")}
      >
        <div className={styles.error}>
          <p>{t("widgetError")}</p>
        </div>
        <figcaption className={styles.caption}>
          <span className={styles.title}>{title}</span>
          <p>{t("widgetFallback")}</p>
        </figcaption>
      </figure>
    );
  }

  return (
    <figure className={styles.figure} role="application" aria-label={title}>
      <iframe
        ref={iframeRef}
        src="about:blank"
        sandbox="allow-scripts"
        className={styles.iframe}
        title={title}
        aria-label={title}
      />
      {!isReady && (
        <div
          className={styles.loadingOverlay}
          role="status"
          aria-label={t("widgetLoading")}
        >
          <div className={styles.spinner} aria-hidden="true" />
        </div>
      )}
      <figcaption className={styles.caption}>
        <span className={styles.title}>{title}</span>
      </figcaption>
    </figure>
  );
}
