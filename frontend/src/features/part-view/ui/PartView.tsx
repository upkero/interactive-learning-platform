"use client";

import { useState, useCallback, useMemo } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/shared/i18n/navigation";
import { ActionLink } from "@/shared/ui/action-link/ActionLink";
import { usePart } from "@/entities/part";
import { useDocument } from "@/entities/document";
import { PartMarkdown } from "./PartMarkdown";
import { useApiErrorMessage } from "@/shared/api";
import { PageShell } from "@/shared/ui/page-shell/PageShell";
import { Surface } from "@/shared/ui/surface/Surface";
import type { ChoiceQuiz, OrderingQuiz, NumericQuiz } from "@/entities/part";
import styles from "./PartView.module.css";

interface PartViewProps {
  partId: string;
  renderWidgetActions?: (widgetId: string, partId: string) => React.ReactNode;
  renderQuiz?: (
    quiz: ChoiceQuiz | OrderingQuiz | NumericQuiz
  ) => React.ReactNode;
  renderShareAction?: () => React.ReactNode;
}

export function PartView({
  partId,
  renderWidgetActions,
  renderQuiz,
  renderShareAction,
}: PartViewProps) {
  const t = useTranslations("viewer");
  const tCommon = useTranslations("common");
  const tProgress = useTranslations("progress");
  const tEmpty = useTranslations("empty");
  const locale = useLocale();

  const [showTOC, setShowTOC] = useState(true);
  const [selectedSectionIndex, setSelectedSectionIndex] = useState<
    number | null
  >(null);

  const partQuery = usePart(partId);
  const part = partQuery.data;

  const documentQuery = useDocument(part?.document_id ?? null, {
    enabled: !!part?.document_id,
  });
  const document = documentQuery.data;

  const partContent = part?.content;

  const images = partContent?.images ?? {};
  const quizzes = partContent?.quizzes ?? [];
  const sections = partContent?.sections ?? [];
  const keyTerms = partContent?.key_terms ?? [];
  const markdown = partContent?.markdown ?? "";
  const documentParts = document?.parts ?? [];

  // Transform widgets to WidgetSlot format
  const widgets = useMemo<
    Record<
      string,
      {
        key: string;
        title: string;
        status: "pending" | "fallback" | "ready";
        fallback?: unknown;
        config?: unknown;
        code?: unknown;
      }
    >
  >(() => {
    const result: Record<
      string,
      {
        key: string;
        title: string;
        status: "pending" | "fallback" | "ready";
        fallback?: unknown;
        config?: unknown;
        code?: unknown;
      }
    > = {};
    for (const [key, widget] of Object.entries(partContent?.widgets ?? {})) {
      if ("status" in widget) {
        const pendingWidget = widget as {
          status: "pending" | "fallback";
          title: string;
          fallback: unknown;
        };
        result[key] = {
          key,
          title: pendingWidget.title,
          status: pendingWidget.status,
          fallback: pendingWidget.fallback,
        };
      } else if ("kind" in widget) {
        const typedWidget = widget as { kind: string; title: string };
        if (typedWidget.kind === "config") {
          result[key] = {
            key,
            title: typedWidget.title,
            status: "ready",
            config: widget,
          };
        } else if (typedWidget.kind === "code") {
          result[key] = {
            key,
            title: typedWidget.title,
            status: "ready",
            code: widget,
          };
        }
      }
    }
    return result;
  }, [partContent?.widgets]);

  // Get error message for part query error at top level (hook rules)
  const partQueryErrorMessage = useApiErrorMessage(partQuery.error);
  const documentQueryErrorMessage = useApiErrorMessage(documentQuery.error);

  const handleBackToMaterials = useCallback(() => {
    window.history.back();
  }, []);

  // Loading state
  if (partQuery.isPending || (part?.document_id && documentQuery.isPending)) {
    return (
      <PageShell title={t("materialTitle")}>
        <PartViewSkeleton />
      </PageShell>
    );
  }

  // Error state
  if (partQuery.isError) {
    return (
      <PageShell title={t("materialTitle")}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <h2 className={styles.errorTitle}>{t("loadError")}</h2>
            <p className={styles.errorMessage}>{partQueryErrorMessage}</p>
            <button
              type="button"
              className={styles.retryBtn}
              onClick={() => void partQuery.refetch()}
            >
              {tCommon("retry")}
            </button>
            <ActionLink
              href={`/${locale}/materials`}
              className={styles.backLink}
            >
              {tCommon("back")}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  if (part?.document_id && documentQuery.isError) {
    return (
      <PageShell title={t("materialTitle")}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <h2 className={styles.errorTitle}>{t("loadError")}</h2>
            <p className={styles.errorMessage}>{documentQueryErrorMessage}</p>
            <button
              type="button"
              className={styles.retryBtn}
              onClick={() => void documentQuery.refetch()}
            >
              {tCommon("retry")}
            </button>
            <ActionLink
              href={`/${locale}/materials`}
              className={styles.backLink}
            >
              {tCommon("back")}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  if (!part) {
    return (
      <PageShell title={t("materialTitle")}>
        <Surface>
          <div className={styles.emptyState} role="status">
            <p>{tEmpty("materialsAll")}</p>
            <ActionLink
              href={`/${locale}/materials`}
              className={styles.backLink}
            >
              {tCommon("back")}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  const isOwner = document?.role === "owner";

  return (
    <PageShell
      title={part.title}
      actions={
        <>
          <ActionLink
            href={`/${locale}/materials`}
            variant="secondary"
            onClick={handleBackToMaterials}
            className={styles.backLink}
          >
            {tCommon("back")}
          </ActionLink>
          {renderShareAction && isOwner && renderShareAction()}
        </>
      }
    >
      <div className={styles.layout}>
        {showTOC && (documentParts.length > 1 || sections.length > 0) && (
          <aside className={styles.toc} aria-label={t("tocTitle")}>
            <Surface title={t("tocTitle")}>
              <nav className={styles.tocNav}>
                {documentParts.length > 1 && (
                  <>
                    <h3 className={styles.tocSectionTitle}>
                      {t("documentParts")}
                    </h3>
                    <ul className={styles.tocList} role="list">
                      {documentParts.map((docPart) => (
                        <li key={docPart.id} className={styles.tocItem}>
                          <Link
                            href={`/${locale}/parts/${docPart.id}`}
                            className={`${styles.tocLink} ${docPart.id === partId ? styles.active : ""} ${docPart.status === "failed" ? styles.failed : ""}`}
                            aria-current={
                              docPart.id === partId ? "page" : undefined
                            }
                          >
                            <span className={styles.tocIndex}>
                              {docPart.index + 1}
                            </span>
                            <span className={styles.tocTitle}>
                              {docPart.title}
                            </span>
                            <span
                              className={`${styles.tocStatus} ${styles[`status${docPart.status.charAt(0).toUpperCase() + docPart.status.slice(1)}`]}`}
                            >
                              {tProgress(`partStatus.${docPart.status}`)}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </>
                )}

                {sections.length > 0 && (
                  <>
                    <h3 className={styles.tocSectionTitle}>
                      {t("currentPartSections")}
                    </h3>
                    <ul className={styles.tocList} role="list">
                      {sections.map((section, index) => (
                        <li key={section.anchor} className={styles.tocItem}>
                          <button
                            type="button"
                            className={`${styles.tocLink} ${selectedSectionIndex === index ? styles.active : ""}`}
                            onClick={() => {
                              setSelectedSectionIndex(index);
                            }}
                            aria-current={
                              selectedSectionIndex === index
                                ? "page"
                                : undefined
                            }
                          >
                            <span className={styles.tocIndex}>
                              {section.page ?? index + 1}
                            </span>
                            <span className={styles.tocTitle}>
                              {section.title}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </nav>

              {(documentParts.length > 1 || sections.length > 0) && (
                <button
                  type="button"
                  className={styles.tocToggle}
                  onClick={() => {
                    setShowTOC(false);
                  }}
                  aria-label={t("closeTOC")}
                >
                  {t("closeTOC")}
                </button>
              )}
            </Surface>
          </aside>
        )}

        <main className={styles.content}>
          {showTOC && (documentParts.length > 1 || sections.length > 0) && (
            <button
              type="button"
              className={styles.tocMobileToggle}
              onClick={() => {
                setShowTOC(true);
              }}
              aria-label={t("tocTitle")}
            >
              {t("tocTitle")}
            </button>
          )}

          <Surface>
            {partContent?.title && (
              <h1 className={styles.partTitle}>{partContent.title}</h1>
            )}

            {markdown && (
              <PartMarkdown
                markdown={markdown}
                widgets={
                  widgets as Record<
                    string,
                    import("@/features/part-view").WidgetSlot
                  >
                }
                images={images}
                quizzes={quizzes}
                renderQuiz={renderQuiz}
                renderWidgetActions={renderWidgetActions}
                partId={partId}
              />
            )}

            {keyTerms.length > 0 && (
              <section
                className={styles.keyTerms}
                aria-labelledby="key-terms-heading"
              >
                <h2 id="key-terms-heading" className={styles.keyTermsTitle}>
                  {t("keyTermsTitle")}
                </h2>
                <ul className={styles.keyTermsList} role="list">
                  {keyTerms.map((term, index) => (
                    <li key={index} className={styles.keyTermItem}>
                      <span className={styles.keyTermName}>{term}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {sections.length > 0 && document?.source_url && (
              <section
                className={styles.sources}
                aria-labelledby="sources-heading"
              >
                <h2 id="sources-heading" className={styles.sourcesTitle}>
                  {t("sourcesTitle")}
                </h2>
                <ul className={styles.sourcesList} role="list">
                  {sections.map((section, index) => {
                    const pageNumber: number = section.page ?? index + 1;
                    const pageStr = String(pageNumber);
                    return (
                      <li key={section.anchor} className={styles.sourceItem}>
                        <a
                          // eslint-disable-next-line @typescript-eslint/restrict-template-expressions
                          href={`${document.source_url}#page=${pageStr}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={styles.sourceLink}
                        >
                          {t("sourceLink", { page: pageStr })}
                        </a>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}

            <footer className={styles.footer}>
              <Link
                href={`/${locale}/parts/${partId}/quiz`}
                className={styles.quizButton}
                aria-label={t("startQuizButton")}
              >
                {t("startQuizButton")}
              </Link>
            </footer>
          </Surface>
        </main>
      </div>
    </PageShell>
  );
}

function PartViewSkeleton() {
  const tProgress = useTranslations("progress");

  return (
    <div
      className={styles.skeleton}
      role="status"
      aria-label={tProgress("loading")}
    >
      <aside className={styles.tocSkeleton}>
        <Surface>
          <div className={styles.skeletonTocItem} />
          <div className={styles.skeletonTocItem} />
          <div className={styles.skeletonTocItem} />
        </Surface>
      </aside>
      <main className={styles.contentSkeleton}>
        <Surface>
          <div className={styles.skeletonPartHeader} />
          <div className={styles.skeletonContent} />
          <div className={styles.skeletonContent} />
          <div className={styles.skeletonContent} />
        </Surface>
      </main>
    </div>
  );
}
