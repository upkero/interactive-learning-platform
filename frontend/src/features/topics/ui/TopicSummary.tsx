'use client';

import { useTranslations } from 'next-intl';
import type { TopicNodeOut } from '@/entities/document';
import styles from './TopicSummary.module.css';

interface TopicSummaryProps {
  topics: TopicNodeOut[];
  selectedIds: Set<string>;
  quotaRemaining: number | null;
  quotaLoading: boolean;
  quotaError: boolean;
}

export function TopicSummary({
  topics,
  selectedIds,
  quotaRemaining,
  quotaLoading,
  quotaError,
}: TopicSummaryProps) {
  const t = useTranslations('topics');
  const tCommon = useTranslations('common');

  const { selectedCount, partsCount, totalTokens } = calculateSelection(topics, selectedIds);
  const quotaAvailable = quotaRemaining;
  const isOverQuota = quotaAvailable !== null && totalTokens > quotaAvailable;

  if (quotaLoading) {
    return (
      <div className={styles.summary} aria-busy="true">
        <div className={styles.row}>
          <span className={styles.label}>{t('selectedSummary')}</span>
          <span className={styles.value}>{tCommon('loading')}</span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>{t('costSummary')}</span>
          <span className={styles.value}>{tCommon('loading')}</span>
        </div>
        <div className={styles.quotaRow}>
          <span className={styles.label}>{t('quotaLabel')}</span>
          <span className={styles.value}>{tCommon('loading')}</span>
        </div>
      </div>
    );
  }

  if (quotaError) {
    return (
      <div className={styles.summary} role="alert">
        <div className={styles.row}>
          <span className={styles.label}>{t('selectedSummary')}</span>
          <span className={styles.value}>
            {t('selectedSummary', { topics: selectedCount, parts: partsCount })}
          </span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>{t('costSummary')}</span>
          <span className={styles.value}>{totalTokens}</span>
        </div>
        <div className={`${styles.quotaRow} ${styles.error}`}>
          <span className={styles.label}>{t('quotaLabel')}</span>
          <span className={styles.value}>{t('quotaError')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.summary}>
      <div className={styles.row}>
        <span className={styles.label}>{t('selectedLabel')}</span>
        <span className={styles.value}>
          {t('selectedSummary', { topics: selectedCount, parts: partsCount })}
        </span>
      </div>
      <div className={styles.row}>
        <span className={styles.label}>{t('costLabel')}</span>
        <span className={`${styles.value} ${styles.cost} ${isOverQuota ? styles.overQuota : ''}`}>
          {t('costSummary', { cost: totalTokens })}
        </span>
      </div>
      <div className={`${styles.quotaRow} ${isOverQuota ? styles.overQuota : ''}`}>
        <span className={styles.label}>{t('quotaLabel')}</span>
        <span className={styles.value}>
          {quotaAvailable !== null
            ? tCommon('generationsCount', { count: quotaAvailable })
            : t('quotaUnknown')}
        </span>
      </div>
      {isOverQuota && (
        <div className={styles.warning} role="alert">
          {t('quotaWarning')}
        </div>
      )}
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