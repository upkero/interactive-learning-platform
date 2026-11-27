import type { ReactNode } from "react";
import { getTranslations } from "next-intl/server";
import styles from "./layout.module.css";

interface AuthLayoutProps {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}

export default async function AuthLayout({
  children,
  params,
}: AuthLayoutProps) {
  const { locale } = await params;
  const tCommon = await getTranslations({ locale, namespace: "common" });

  return (
    <div className={styles.page}>
      {/* Left panel - Brand */}
      <aside className={styles.leftPanel} aria-hidden="true">
        <div className={styles.leftContent}>
          <div className={styles.brandTop}>
            <a
              href={`/${locale}/materials`}
              className={styles.brand}
              aria-label={tCommon("appName")}
            >
              <span className={styles.brandMark}>
                <svg
                  width="48"
                  height="48"
                  viewBox="0 0 32 32"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  aria-hidden="true"
                >
                  <rect width="32" height="32" rx="8" fill="currentColor" />
                  <path
                    d="M8 16L14 22L24 10"
                    stroke="var(--g-color-bg-dark)"
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
              <span className={styles.brandText}>{tCommon("appName")}</span>
            </a>
          </div>

          <div className={styles.centerSymbol} aria-hidden="true">
            <svg
              width="120"
              height="120"
              viewBox="0 0 120 120"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <circle
                cx="60"
                cy="60"
                r="56"
                stroke="currentColor"
                strokeWidth="1.5"
                opacity="0.3"
              />
              <circle
                cx="60"
                cy="60"
                r="48"
                stroke="currentColor"
                strokeWidth="1"
                opacity="0.2"
              />
              <circle
                cx="60"
                cy="60"
                r="40"
                stroke="currentColor"
                strokeWidth="0.5"
                opacity="0.15"
              />
              <path
                d="M30 60L55 85L90 35"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity="0.6"
              />
            </svg>
          </div>

          <div className={styles.brandBottom}>
            <p className={styles.copyright}>{tCommon("copyright")}</p>
          </div>
        </div>
      </aside>

      {/* Right panel - Form */}
      <main className={styles.rightPanel}>
        <div className={styles.rightContent}>{children}</div>
      </main>
    </div>
  );
}
