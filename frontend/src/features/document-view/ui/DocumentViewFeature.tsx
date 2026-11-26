'use client';

import { useCallback, useState } from 'react';
import { useRouter } from '@/shared/i18n/navigation-client';
import { Link } from '@/shared/i18n/navigation';
import { useTranslations } from 'next-intl';
import Markdown from 'react-markdown';
import { useDocument, useDocumentParts, useDocumentStatusGuard, usePart } from '@/entities/document';
import { ApiError } from '@/shared/api/errors';
import { ActionLink } from '@/shared/ui/action-link/ActionLink';
import { PageShell } from '@/shared/ui/page-shell/PageShell';
import { Surface } from '@/shared/ui/surface/Surface';
import type { PartSummaryOut, PartOut } from '@/entities/document';
import styles from './DocumentViewFeature.module.css';

interface DocumentViewFeatureProps {
  documentId: string;
  initialPartId?: string;
  onShare: () => void;
}

const partStatusLabel = {
  queued: 'partStatus.queued',
  main_pass: 'partStatus.mainPass',
  resolving: 'partStatus.resolving',
  assembling: 'partStatus.assembling',
  published: 'partStatus.published',
  failed: 'partStatus.failed',
} as const satisfies Record<PartSummaryOut['status'], string>;

export function DocumentViewFeature({ documentId, initialPartId, onShare }: DocumentViewFeatureProps) {
  const t = useTranslations('viewer');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');
  const tProgress = useTranslations('progress');
  const tEmpty = useTranslations('empty');

  const router = useRouter();

  const [partId, setSelectedPartId] = useState(initialPartId);
  const [showTOC, setShowTOC] = useState(true);

  const documentQuery = useDocument(documentId);
  const partsQuery = useDocumentParts(documentId);
  const parts = partsQuery.data ?? [];
  const selectedPartId = partId ?? parts[0]?.id ?? null;
  const partQuery = usePart(selectedPartId);

  const document = documentQuery.data;
  const part = partQuery.data;

  // Centralized status guard - document step allows 'done' status (new API)
  const { isLoading, error, hasRedirected: guardRedirected } = useDocumentStatusGuard({
    documentId,
    currentStep: 'document',
    previewPartId: initialPartId,
  });

  const selectedPart = parts.find((p) => p.id === selectedPartId);

  const handleRetry = useCallback(() => {
    void documentQuery.refetch();
    void partsQuery.refetch();
  }, [documentQuery, partsQuery]);

  const handleBackToMaterials = useCallback(() => {
    router.push("/materials");
  }, [router]);

  // Loading state
  if (isLoading || documentQuery.isPending || partsQuery.isPending || (selectedPartId && partQuery.isPending)) {
    return (
      <PageShell title={t('materialTitle')}>
        <DocumentViewSkeleton label={tCommon('loading')} />
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
              {tProgress('documentLoadFailed')}
            </p>
            <div className={styles.errorActions}>
              <ActionLink
                href="/materials"
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
                href="/materials"
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
            <ActionLink href="/materials" variant="primary">
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
              href="/materials"
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
            href="/materials"
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
                          {tProgress(partStatusLabel[part.status])}
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
          {!showTOC && parts.length > 1 && (
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
            {partQuery.isError ? (
              <p role="alert" className={styles.errorMessage}>
                {tErrors(partQuery.error instanceof ApiError ? partQuery.error.code : 'unknown_error')}
              </p>
            ) : selectedPart ? (
              <DocumentPartView
                part={part ?? null}
                summary={selectedPart}
                t={t}
                tProgress={tProgress}
                loadingLabel={tCommon('loading')}
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
  summary: PartSummaryOut;
  t: ReturnType<typeof useTranslations>;
  tProgress: ReturnType<typeof useTranslations>;
  loadingLabel: string;
}

function DocumentPartView({ part, summary, t, tProgress, loadingLabel }: DocumentPartViewProps) {
  const partStatus = part?.status ?? summary.status;
  const partTitle = part?.title ?? summary.title;
  const statusLabel = tProgress(partStatusLabel[partStatus]);
  const partContent = part?.content;

  if (!part) {
    return (
      <article className={styles.partView}>
        <header className={styles.partHeader}>
          <h2 className={styles.partTitle}>{partTitle}</h2>
          <div className={styles.partMeta}>
            <span className={`${styles.partStatus} ${styles[`status${partStatus.charAt(0).toUpperCase() + partStatus.slice(1)}`]}`}>
              {statusLabel}
            </span>
          </div>
        </header>
        <div className={styles.partLoading} role="status" aria-label={loadingLabel}>
          <div className={styles.loadingSpinner} />
          <p>{loadingLabel}</p>
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
            {statusLabel}
          </span>
        </div>
      </header>

      {isFailed && (
        <div className={styles.partError} role="alert">
          <p className={styles.partErrorText}>
            {t('partGenerationFailed')}
          </p>
        </div>
      )}

      {isGenerating ? (
        <div className={styles.partLoading} role="status" aria-label={statusLabel}>
          <div className={styles.loadingSpinner} />
          <p>{statusLabel}</p>
        </div>
      ) : (
        <>
          {partContent?.markdown && (
            <div className={styles.partContent}>
              <div className={styles.markdownContent}>
                <Markdown skipHtml>{partContent.markdown}</Markdown>
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
              href={`/parts/${part.id}/quiz`}
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

function DocumentViewSkeleton({ label }: { label: string }) {
  return (
    <div className={styles.skeleton} role="status" aria-label={label}>
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
