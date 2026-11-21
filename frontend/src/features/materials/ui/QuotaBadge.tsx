'use client';

import { useTranslations } from 'next-intl';
import { useQuota } from '@/entities/user';
import { ApiError } from '@/shared/api/errors';
import styles from './QuotaBadge.module.css';

export function QuotaBadge() {
  const t = useTranslations('materials');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');
  const quota = useQuota();

  if (quota.isPending) {
    return (
      <span className={styles.badge} aria-busy="true">
        <span className={styles.value} aria-hidden="true">—</span>
        <span className={styles.label} aria-live="polite">{tCommon('loading')}</span>
      </span>
    );
  }

  if (quota.isError) {
    const message =
      quota.error instanceof ApiError ? tErrors(quota.error.code) : tErrors('unknown_error');

    return (
      <span className={`${styles.badge} ${styles.error}`} role="status">
        <span className={styles.value} aria-hidden="true">!</span>
        <span className={styles.label}>{message}</span>
        <button type="button" className={styles.retry} onClick={() => void quota.refetch()}>
          {tCommon('retry')}
        </button>
      </span>
    );
  }

  const available = quota.data.available;
  const exhausted = available <= 0;

  return (
    <span className={`${styles.badge} ${exhausted ? styles.exhausted : ''}`}>
      <span className={styles.value} aria-hidden="true">
        <span className={styles.count} data-available={available}>{available}</span>
      </span>
      <span className={styles.label}>
        {exhausted ? t('quotaExhausted') : t('quotaRemaining', { count: available })}
      </span>
    </span>
  );
}