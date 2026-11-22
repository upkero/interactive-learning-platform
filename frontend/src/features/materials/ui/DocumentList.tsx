'use client';

import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { useMaterials, useDeleteDocument, getMaterialRoute, type MaterialOut } from '@/entities/document';
import { ApiError } from '@/shared/api/errors';
import styles from './DocumentList.module.css';

type Scope = 'mine' | 'shared';

interface DocumentListProps {
  scope?: Scope;
}

const STATUS_STYLES: Record<MaterialOut['status'], string> = {
  uploaded: 'status-parsing',
  parsing: 'status-parsing',
  parsed: 'status-topics',
  generating: 'status-generating',
  done: 'status-ready',
  failed: 'status-error',
};

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString(undefined, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function DocumentList({ scope = 'mine' }: DocumentListProps) {
  const t = useTranslations('materials');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');
  const tEmpty = useTranslations('empty');

  const query = useMaterials(scope);
  const deleteMutation = useDeleteDocument();

  if (query.isPending) {
    return (
      <div className={styles.skeletonList} role="status" aria-label={tCommon('loading')}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className={styles.skeletonRow}>
            <div className={styles.skeletonCell} style={{ width: '40%' }} />
            <div className={styles.skeletonCell} style={{ width: '20%' }} />
            <div className={styles.skeletonCell} style={{ width: '15%' }} />
            <div className={styles.skeletonCell} style={{ width: '15%' }} />
          </div>
        ))}
      </div>
    );
  }

  if (query.isError) {
    const message = query.error instanceof ApiError
      ? tErrors(query.error.code)
      : tErrors('unknown_error');

    return (
      <div className={styles.errorState} role="alert">
        <p className={styles.errorMessage}>{message}</p>
        <button
          type="button"
          className={styles.retryButton}
          onClick={() => void query.refetch()}
        >
          {tCommon('retry')}
        </button>
      </div>
    );
  }

  const documents = query.data;

  if (documents.length === 0) {
    const emptyKey = scope === 'mine' ? 'materialsMine' : 'materialsShared';
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyText}>{tEmpty(emptyKey)}</p>
        {scope === 'mine' && (
          <Link href={`/${tCommon('appName').toLowerCase()}/upload`} className={styles.emptyAction}>
            {t('uploadButton')}
          </Link>
        )}
      </div>
    );
  }

  return (
    <>
      {/* Desktop: Table layout */}
      <div className={styles.tableWrapper} hidden={false}>
        <table className={styles.table} role="grid">
          <thead>
            <tr>
              <th scope="col" className={styles.headerCell}>{t('title')}</th>
              <th scope="col" className={styles.headerCell}>{t('status')}</th>
              <th scope="col" className={styles.headerCell}>{t('createdAt')}</th>
              <th scope="col" className={styles.headerCell}>{t('actions')}</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <DocumentRow key={doc.document_id} doc={doc} deleteMutation={deleteMutation} />
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile: Card layout */}
      <div className={styles.cardList} aria-label={t('title')}>
        {documents.map((doc) => (
          <DocumentCard key={doc.document_id} doc={doc} deleteMutation={deleteMutation} />
        ))}
      </div>
    </>
  );
}

interface DocumentRowProps {
  doc: MaterialOut;
  deleteMutation: ReturnType<typeof useDeleteDocument>;
}

function DocumentRow({ doc, deleteMutation }: DocumentRowProps) {
  const t = useTranslations('materials');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');

  const statusStyle = STATUS_STYLES[doc.status];

  const handleClick = (e: React.MouseEvent<HTMLTableRowElement> | React.KeyboardEvent<HTMLTableRowElement>) => {
    // Don't navigate if clicking on interactive elements (buttons)
    if ('currentTarget' in e && 'target' in e && e.currentTarget !== e.target) return;

    if (doc.status === 'failed') {
      // For error status, stay on page - actions are inline
      return;
    }
    // Navigation is handled by the Link in the title cell
  };

  const handleDelete = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (!window.confirm(t('deleteConfirm', { title: doc.title }))) return;

    void deleteMutation.mutateAsync().catch((error: unknown) => {
      const message = error instanceof ApiError
        ? tErrors(error.code)
        : tErrors('unknown_error');
      alert(message);
    });
  };

  const handleRetry = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    // For error state, we could trigger a re-parse or re-generation
    // This would depend on the API - for now, we'll just show an alert
    alert(t('retryNotImplemented'));
  };

  return (
    <tr className={styles.row} onClick={handleClick} tabIndex={0} role="button" onKeyDown={(e) => { if (e.key === 'Enter') handleClick(e); }}>
      <td className={styles.cell}>
        {doc.status === 'failed' ? (
          <span className={styles.titleText}>
            {doc.title}
            {doc.role === 'shared' && (
              <span className={styles.sharedBadge} aria-label={t('sharedLabel')}>
                {t('sharedLabel')}
              </span>
            )}
          </span>
        ) : (
          <Link href={getMaterialRoute(doc)} className={styles.titleLink}>
            {doc.title}
            {doc.role === 'shared' && (
              <span className={styles.sharedBadge} aria-label={t('sharedLabel')}>
                {t('sharedLabel')}
              </span>
            )}
          </Link>
        )}
      </td>
      <td className={styles.cell}>
        <span className={`${styles.statusBadge} ${styles[statusStyle]}`}>
          {t(`status.${doc.status}`)}
        </span>
      </td>
      <td className={styles.cell}>
        <time dateTime={doc.updated_at}>{formatDate(doc.updated_at)}</time>
      </td>
      <td className={styles.cell}>
        <div className={styles.actions}>
          {doc.status === 'failed' && (
            <>
              <button
                type="button"
                className={styles.actionButton}
                onClick={handleRetry}
              >
                {t('retryAction')}
              </button>
              <button
                type="button"
                className={`${styles.actionButton} ${styles.danger}`}
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? tCommon('loading') : tCommon('delete')}
              </button>
            </>
          )}
          {doc.status !== 'failed' && (
            <button
              type="button"
              className={styles.actionButton}
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? tCommon('loading') : tCommon('delete')}
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}
interface DocumentCardProps {
  doc: MaterialOut;
  deleteMutation: ReturnType<typeof useDeleteDocument>;
}

function DocumentCard({ doc, deleteMutation }: DocumentCardProps) {
  const t = useTranslations('materials');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');

  const statusStyle = STATUS_STYLES[doc.status];

  const handleDelete = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (!window.confirm(t('deleteConfirm', { title: doc.title }))) return;

    void deleteMutation.mutateAsync().catch((error: unknown) => {
      const message = error instanceof ApiError
        ? tErrors(error.code)
        : tErrors('unknown_error');
      alert(message);
    });
  };

  const handleRetry = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    alert(t('retryNotImplemented'));
  };

  return (
    <article className={styles.card} role="listitem">
      <header className={styles.cardHeader}>
        <div>
          <Link href={getMaterialRoute(doc)} className={styles.cardTitle}>
            {doc.title}
            {doc.role === 'shared' && (
              <span className={styles.sharedBadge} aria-label={t('sharedLabel')}>
                {t('sharedLabel')}
              </span>
            )}
          </Link>
        </div>
      </header>

      <div className={styles.cardMeta}>
        <span className={`${styles.cardStatus} ${styles[statusStyle]}`}>
          {t(`status.${doc.status}`)}
        </span>
        <time dateTime={doc.updated_at} className={styles.cardDate}>
          {formatDate(doc.updated_at)}
        </time>
      </div>

      <footer className={styles.cardActions}>
        {doc.status === 'failed' && (
          <>
            <button
              type="button"
              className={styles.actionButton}
              onClick={handleRetry}
            >
              {t('retryAction')}
            </button>
            <button
              type="button"
              className={`${styles.actionButton} ${styles.danger}`}
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? tCommon('loading') : tCommon('delete')}
            </button>
          </>
        )}
        {doc.status !== 'failed' && (
          <button
            type="button"
            className={styles.actionButton}
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? tCommon('loading') : tCommon('delete')}
          </button>
        )}
      </footer>
    </article>
  );
}
