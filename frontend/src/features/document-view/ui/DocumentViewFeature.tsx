'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { useDocument, useDocumentParts, usePart } from '@/entities/document';
import { useDocumentStatusGuard } from '@/entities/document/guard/useDocumentStatusGuard';
import { ApiError } from '@/shared/api/errors';
import { ActionLink } from '@/shared/ui/action-link/ActionLink';
import { PageShell } from '@/shared/ui/page-shell/PageShell';
import { Surface } from '@/shared/ui/surface/Surface';
import type { PartSummaryOut, PartOut } from '@/entities/document';
import styles from './DocumentViewFeature.module.css';

interface DocumentViewFeatureProps {
  documentId: string;
  onShare: () => void;
}

export function DocumentViewFeature({ documentId, onShare }: DocumentViewFeatureProps) {
  const t = useTranslations('viewer');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');
  const tProgress = useTranslations('progress');
  const tEmpty = useTranslations('empty');

  const router = useRouter();
  const locale = useLocale();

  const [selectedPartId, setSelectedPartId] = useState<string | null>(null);
  const [showTOC, setShowTOC] = useState(true);

  const documentQuery = useDocument(documentId);
  const partsQuery = useDocumentParts(documentId);
  const partQuery = usePart(selectedPartId);

  const document = documentQuery.data;
  const parts = partsQuery.data ?? [];
  const part = partQuery.data;

  // Centralized status guard - document step allows 'done' status (new API)
  const { isLoading, error, hasRedirected: guardRedirected } = useDocumentStatusGuard({
    documentId,
    currentStep: 'document',
  });

  // Auto-select first part if none selected
  if (!selectedPartId && parts.length > 0) {
    setSelectedPartId(parts[0].id);
  }

  const selectedPart = parts.find((p) => p.id === selectedPartId);

  const handleRetry = useCallback(() => {
    void documentQuery.refetch();
    void partsQuery.refetch();
  }, [documentQuery, partsQuery]);

  const handleBackToMaterials = useCallback(() => {
    router.push(`/${locale}/materials`);
  }, [router, locale]);

  // Loading state
  if (isLoading || documentQuery.isPending || partsQuery.isPending || (selectedPartId && partQuery.isPending)) {
    return (
      <PageShell title={t('materialTitle')}>
        <DocumentViewSkeleton />
      </PageShell>
    );
  }

  // Error state for guard
  if (error) {
    return (
      <PageShell title={t('materialTitle')}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <h2 className={styles.errorTitle}>{t('loadError')}</h2>
            <p className={styles.errorMessage}>
              Не удалось загрузить документ. Возможно, он был удален или у вас нет доступа.
            </p>
            <div className={styles.errorActions}>
              <ActionLink
                href={`/${locale}/materials`}
                variant="secondary"
                className={styles.actionButton}
              >
                {tCommon('back')}
              </ActionLink>
            </div>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // Error state for queries
  if (documentQuery.isError || partsQuery.isError) {
    const queryError = documentQuery.error ?? partsQuery.error;
    const message = queryError instanceof ApiError
      ? tErrors(queryError.code)
      : tErrors('unknown_error');

    return (
      <PageShell title={t('materialTitle')}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <h2 className={styles.errorTitle}>{t('loadError')}</h2>
            <p className={styles.errorMessage}>{message}</p>
            <div className={styles.errorActions}>
              <button
                type="button"
                className={`${styles.actionButton} ${styles.primary}`}
                onClick={handleRetry}
              >
                {tCommon('retry')}
              </button>
              <ActionLink
                href={`/${locale}/materials`}
                variant="secondary"
                className={styles.actionButton}
              >
                {tCommon('back')}
              </ActionLink>
            </div>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // Document not found
  if (!document) {
    return (
      <PageShell title={t('materialTitle')}>
        <Surface>
          <div className={styles.emptyState} role="status">
            <p>{tEmpty('materialsAll')}</p>
            <ActionLink href={`/${locale}/materials`} variant="primary">
              {tCommon('back')}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  if (guardRedirected) {
    return null;
  }

  // Empty parts
  if (parts.length === 0) {
    return (
      <PageShell
        title={document.title}
        actions={
          <div className={styles.headerActions}>
            <ActionLink
              href={`/${locale}/materials`}
              variant="secondary"
              onClick={handleBackToMaterials}
            >
              {tCommon('back')}
            </ActionLink>
            <button
              type="button"
              className={styles.shareButton}
              onClick={onShare}
              aria-label={t('shareLabel')}
            >
              {t('shareLabel')}
            </button>
          </div>
        }
      >
        <Surface title={t('tocTitle')}>
          <p className={styles.emptyMessage}>{tEmpty('topicsNone')}</p>
        </Surface>
      </PageShell>
    );
  }

  return (
    <PageShell
      title={document.title}
      actions={
        <div className={styles.headerActions}>
          <ActionLink
            href={`/${locale}/materials`}
            variant="secondary"
            onClick={handleBackToMaterials}
          >
            {tCommon('back')}
          </ActionLink>
          <button
            type="button"
            className={styles.shareButton}
            onClick={onShare}
            aria-label={t('shareLabel')}
          >
            {t('shareLabel')}
          </button>
        </div>
      }
    >
      <div className={styles.layout}>
        {showTOC && parts.length > 1 && (
          <aside className={styles.toc} aria-label={t('tocTitle')}>
            <Surface title={t('tocTitle')}>
              <nav className={styles.tocNav}>
                <ul className={styles.tocList} role="list">
                  {parts.map((part) => (
                    <li key={part.id} className={styles.tocItem}>
                      <button
                        type="button"
                        className={`${styles.tocLink} ${selectedPartId === part.id ? styles.active : ''} ${part.status === 'failed' ? styles.failed : ''}`}
                        onClick={() => { setSelectedPartId(part.id); }}
                        aria-current={selectedPartId === part.id ? 'page' : undefined}
                        disabled={part.status === 'queued' || part.status === 'main_pass' || part.status === 'resolving' || part.status === 'assembling'}
                      >
                        <span className={styles.tocIndex}>{part.index + 1}</span>
                        <span className={styles.tocTitle}>{part.title}</span>
                        <span className={`${styles.tocStatus} ${styles[`status${part.status.charAt(0).toUpperCase() + part.status.slice(1)}`]}`}>
                          {tProgress(`partStatus.${part.status}`)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </nav>
              {parts.length > 1 && (
                <button
                  type="button"
                  className={styles.tocToggle}
                  onClick={() => { setShowTOC(false); }}
                  aria-label={t('closeTOC')}
                >
                  {t('closeTOC')}
                </button>
              )}
            </Surface>
          </aside>
        )}

        <main className={styles.content}>
          {showTOC && parts.length > 1 && (
            <button
              type="button"
              className={styles.tocMobileToggle}
              onClick={() => { setShowTOC(true); }}
              aria-label={t('tocTitle')}
            >
              {t('tocTitle')}
            </button>
          )}

          <Surface>
            {selectedPart ? (
              <DocumentPartView
                part={part ?? null}
                summary={selectedPart}
                locale={locale}
                t={t}
                tProgress={tProgress}
              />
            ) : (
              <p className={styles.emptyMessage}>{tEmpty('topicsNone')}</p>
            )}
          </Surface>
        </main>
      </div>
    </PageShell>
  );
}

interface DocumentPartViewProps {
  part: PartOut | null;
  summary: PartSummaryOut | undefined;
  locale: string;
  t: ReturnType<typeof useTranslations>;
  tProgress: ReturnType<typeof useTranslations>;
}

function DocumentPartView({ part, summary, locale, t, tProgress }: DocumentPartViewProps) {
  const partStatus = summary?.status || part?.status || '';
  const partTitle = summary?.title || part?.title || '';
  const partContent = part?.content;

  if (!part) {
    return (
      <article className={styles.partView}>
        <header className={styles.partHeader}>
          <h2 className={styles.partTitle}>{partTitle}</h2>
          <div className={styles.partMeta}>
            <span className={`${styles.partStatus} ${styles[`status${partStatus.charAt(0).toUpperCase() + partStatus.slice(1)}`]}`}>
              {tProgress(`partStatus.${partStatus}`)}
            </span>
          </div>
        </header>
        <div className={styles.partLoading} role="status" aria-label={tProgress('loading')}>
          <div className={styles.loadingSpinner} />
          <p>{tProgress('loading')}</p>
        </div>
      </article>
    );
  }

  const isGenerating = partStatus === 'queued' || partStatus === 'main_pass' || partStatus === 'resolving' || partStatus === 'assembling';
  const isFailed = partStatus === 'failed';

  return (
    <article className={styles.partView}>
      <header className={styles.partHeader}>
        <h2 className={styles.partTitle}>{partTitle}</h2>
        <div className={styles.partMeta}>
          <span className={`${styles.partStatus} ${styles[`status${partStatus.charAt(0).toUpperCase() + partStatus.slice(1)}`]}`}>
            {tProgress(`partStatus.${partStatus}`)}
          </span>
        </div>
      </header>

      {isFailed && (
        <div className={styles.partError} role="alert">
          <p className={styles.partErrorText}>
            {useTranslations('errors')('part_generation_failed' as keyof ReturnType<typeof useTranslations>)}
          </p>
          <p className={styles.partErrorHint}>{tProgress('partFailedHint')}</p>
          <button type="button" className={styles.retryPartButton} disabled>
            {tProgress('retryPartButton')}
          </button>
        </div>
      )}

      {isGenerating ? (
        <div className={styles.partLoading} role="status" aria-label={tProgress('partStatus.generating')}>
          <div className={styles.loadingSpinner} />
          <p>{tProgress(`partStatus.${partStatus}`)}</p>
        </div>
      ) : (
        <>
          {partContent?.markdown && (
            <div className={styles.partContent}>
              <div className={styles.markdownContent}>
                {renderMarkdown(partContent.markdown)}
              </div>
            </div>
          )}

          {partContent?.widgets && Object.keys(partContent.widgets).length > 0 && (
            <div className={styles.widgetsSection}>
              {Object.entries(partContent.widgets).map(([widgetId, widget]) => {
                if ('status' in widget && widget.status === 'pending') {
                  return (
                    <div key={widgetId} className={styles.widgetPlaceholder} role="status">
                      <div className={styles.widgetSpinner} />
                      <p>{t('widgetPending')}</p>
                    </div>
                  );
                }
                if ('status' in widget && widget.status === 'fallback') {
                  return (
                    <div key={widgetId} className={styles.widgetFallback} role="note">
                      <p>{t('widgetFallback')}</p>
                    </div>
                  );
                }
                return null;
              })}
            </div>
          )}

          {partContent?.key_terms && partContent.key_terms.length > 0 && (
            <section className={styles.keyTerms} aria-labelledby="key-terms-heading">
              <h3 id="key-terms-heading" className={styles.keyTermsTitle}>{t('keyTermsTitle')}</h3>
              <dl className={styles.keyTermsList}>
                {partContent.key_terms.map((kt: string, index: number) => (
                  <div key={index} className={styles.keyTermItem}>
                    <dt className={styles.keyTermName}>{kt}</dt>
                  </div>
                ))}
              </dl>
            </section>
          )}

          <footer className={styles.partFooter}>
            <Link
              href={`/${locale}/parts/${part.id}/quiz`}
              className={styles.quizButton}
              aria-label={t('startQuizButton')}
            >
              {t('startQuizButton')}
            </Link>
          </footer>
        </>
      )}
    </article>
  );
}

function DocumentViewSkeleton() {
  return (
    <div className={styles.skeleton} role="status" aria-label="Загрузка материала...">
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

// Simple markdown renderer - in production, use react-markdown or similar
function renderMarkdown(content: string) {
  // For now, just render as pre-formatted text with basic formatting
  // TODO: Replace with react-markdown + remark-gfm + rehype-katex when available
  const lines = content.split('\n');
  return (
    <div className={styles.markdownBody}>
      {lines.map((line, index) => (
        <p key={index} className={styles.markdownLine}>
          {line || <br />}
        </p>
      ))}
    </div>
  );
}