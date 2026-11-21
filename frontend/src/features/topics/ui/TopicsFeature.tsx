'use client';

import { useCallback, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useDocumentTopics } from '@/entities/document';
import { useQuota } from '@/entities/user';
import { useDocumentStatusGuard } from '@/entities/document/guard/useDocumentStatusGuard';
import { ApiError } from '@/shared/api/errors';
import { TopicTree } from './TopicTree';
import { TopicSummary } from './TopicSummary';
import { ActionLink } from '@/shared/ui/action-link/ActionLink';
import { PageShell } from '@/shared/ui/page-shell/PageShell';
import { Surface } from '@/shared/ui/surface/Surface';
import type { TopicNodeOut } from '@/entities/document';
import styles from './TopicsFeature.module.css';

// Type aliases for compatibility with selection functions
type TopicNode = TopicNodeOut;

export function TopicsFeature({ documentId }: { documentId: string }) {
  const t = useTranslations('topics');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');
  const tEmpty = useTranslations('empty');

  const router = useRouter();
  const searchParams = useSearchParams();
  const locale = searchParams.get('locale') || 'ru';

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isSubmitting, setIsSubmitting] = useState(false);

  const topicsQuery = useDocumentTopics(documentId);
  const quotaQuery = useQuota();

  // Centralized status guard - topics step allows 'topics_required' status
  const { isLoading, error, hasRedirected: guardRedirected } = useDocumentStatusGuard({
    documentId,
    currentStep: 'topics',
  });

  const topics = topicsQuery.data ?? [];

  const { selectedCount, totalTokens } = useMemo(
    () => calculateSelection(topics, selectedIds),
    [topics, selectedIds]
  );

  const quotaAvailable = quotaQuery.data?.available ?? null;
  const isOverQuota = quotaAvailable !== null && totalTokens > quotaAvailable;

  const quotaRemaining = quotaAvailable; // Alias for TopicSummary prop
  const canProceed = selectedCount > 0 && !isOverQuota && !isSubmitting;

  const handleTopicToggle = useCallback((id: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        addIdAndDescendants(next, id, topics);
      } else {
        removeIdAndDescendants(next, id, topics);
      }
      return next;
    });
  }, [topics]);

  const handleSelectAll = useCallback(() => {
    const allIds = new Set<string>();
    collectAllIds(topics, allIds);
    setSelectedIds(allIds);
  }, [topics]);

  const handleDeselectAll = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const handleRetryTopics = useCallback(() => {
    void topicsQuery.refetch();
  }, [topicsQuery]);

  const handleNext = useCallback(() => {
    if (!canProceed) return;

    setIsSubmitting(true);
    try {
      // Store selected topic IDs in session storage for the next page
      sessionStorage.setItem(`topics_${documentId}`, JSON.stringify(Array.from(selectedIds)));
      // Navigate to questions page
      router.push(`/${locale}/documents/${documentId}/questions`);
    } catch {
      // Navigation error - will be handled by router
    } finally {
      setIsSubmitting(false);
    }
  }, [canProceed, documentId, router, locale, selectedIds]);

  // Loading state
  if (isLoading) {
    return (
      <PageShell title={t('title')}>
        <TopicsSkeleton />
      </PageShell>
    );
  }

  // Error state for topics
  if (topicsQuery.isError) {
    const message = topicsQuery.error instanceof ApiError
      ? tErrors(topicsQuery.error.code)
      : tErrors('unknown_error');

    return (
      <PageShell title={t('title')}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <p className={styles.errorMessage}>{message}</p>
            <button type="button" className={styles.retryButton} onClick={handleRetryTopics}>
              {tCommon('retry')}
            </button>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // Error state for guard
  if (error) {
    return (
      <PageShell title={t('title')}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <p className={styles.errorMessage}>
              Не удалось загрузить документ. Возможно, он был удален или у вас нет доступа.
            </p>
            <ActionLink
              href={`/${locale}/materials`}
              variant="secondary"
              className={styles.retryButton}
            >
              {tCommon('back')}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // Empty topics
  if (topics.length === 0) {
    return (
      <PageShell title={t('title')}>
        <Surface title={t('planPreviewTitle')}>
          <p className={styles.emptyText}>{tEmpty('topicsNone')}</p>
        </Surface>
        <div className={styles.actions}>
          <ActionLink
            href={`/${locale}/materials`}
            variant="secondary"
          >
            {tCommon('back')}
          </ActionLink>
        </div>
      </PageShell>
    );
  }

  if (guardRedirected) {
    return null;
  }

  return (
    <PageShell
      title={t('title')}
      actions={
        <ActionLink
          href={`/${locale}/documents/${documentId}/questions`}
          variant="primary"
          onClick={handleNext}
          disabled={!canProceed || isSubmitting}
          aria-disabled={!canProceed || isSubmitting}
        >
          {isSubmitting ? tCommon('loading') : tCommon('next')}
        </ActionLink>
      }
    >
      <Surface title={t('planPreviewTitle')}>
        <div className={styles.toolbar}>
          <div className={styles.toolbarActions}>
            <button
              type="button"
              className={styles.toolbarButton}
              onClick={handleSelectAll}
              disabled={selectedCount === topics.length}
            >
              {t('selectAll')}
            </button>
            <button
              type="button"
              className={styles.toolbarButton}
              onClick={handleDeselectAll}
              disabled={selectedCount === 0}
            >
              {t('deselectAll')}
            </button>
          </div>
        </div>

        <TopicTree
          topics={topics}
          selectedIds={selectedIds}
          onToggle={handleTopicToggle}
          disabled={isSubmitting}
        />
      </Surface>

      <TopicSummary
        topics={topics}
        selectedIds={selectedIds}
        quotaRemaining={quotaRemaining}
        quotaLoading={quotaQuery.isPending}
        quotaError={quotaQuery.isError}
      />
    </PageShell>
  );
}

function TopicsSkeleton() {
  return (
    <div className={styles.skeleton} role="status" aria-label="Загрузка тем...">
      <Surface>
        <div className={styles.skeletonToolbar}>
          <div className={styles.skeletonButton} />
          <div className={styles.skeletonButton} />
        </div>
        <div className={styles.skeletonTree}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className={styles.skeletonItem}>
              <div className={styles.skeletonCheckbox} />
              <div className={styles.skeletonTitle} style={{ width: '60%' }} />
              <div className={styles.skeletonCost} />
            </div>
          ))}
        </div>
      </Surface>
      <div className={styles.skeletonSummary}>
        <Surface>
          <div className={styles.skeletonRow}>
            <div className={styles.skeletonLabel} />
            <div className={styles.skeletonValue} />
          </div>
          <div className={styles.skeletonRow}>
            <div className={styles.skeletonLabel} />
            <div className={styles.skeletonValue} />
          </div>
          <div className={styles.skeletonRow}>
            <div className={styles.skeletonLabel} />
            <div className={styles.skeletonValue} />
          </div>
        </Surface>
      </div>
    </div>
  );
}

interface SelectionStats {
  selectedCount: number;
  partsCount: number;
  totalTokens: number;
}

function calculateSelection(topics: TopicNodeOut[], selectedIds: Set<string>): SelectionStats {
  let selectedCount = 0;
  let partsCount = 0;
  let totalTokens = 0;

  for (const topic of topics) {
    if (selectedIds.has(topic.id)) {
      selectedCount += 1;
      partsCount += 1;
      totalTokens += topic.tokens;
    }
    if (topic.children.length > 0) {
      const childStats = calculateSelection(topic.children, selectedIds);
      selectedCount += childStats.selectedCount;
      partsCount += childStats.partsCount;
      totalTokens += childStats.totalTokens;
    }
  }

  return { selectedCount, partsCount, totalTokens };
}

function collectAllIds(topics: TopicNode[], ids: Set<string>) {
  for (const topic of topics) {
    ids.add(topic.id);
    if (topic.children.length > 0) {
      collectAllIds(topic.children, ids);
    }
  }
}

function addIdAndDescendants(ids: Set<string>, id: string, topics: TopicNode[]) {
  for (const topic of topics) {
    if (topic.id === id) {
      ids.add(topic.id);
      if (topic.children.length > 0) {
        collectAllIds(topic.children, ids);
      }
      return;
    }
    if (topic.children.length > 0) {
      addIdAndDescendants(ids, id, topic.children);
    }
  }
}

function removeIdAndDescendants(ids: Set<string>, id: string, topics: TopicNode[]) {
  for (const topic of topics) {
    if (topic.id === id) {
      ids.delete(topic.id);
      if (topic.children.length > 0) {
        removeAllDescendants(ids, topic.children);
      }
      return;
    }
    if (topic.children.length > 0) {
      removeIdAndDescendants(ids, id, topic.children);
    }
  }
}

function removeAllDescendants(ids: Set<string>, topics: TopicNode[]) {
  for (const topic of topics) {
    ids.delete(topic.id);
    if (topic.children.length > 0) {
      removeAllDescendants(ids, topic.children);
    }
  }
}