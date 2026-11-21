'use client';

import { useLocale, useTranslations } from 'next-intl';
import { usePathname, useRouter } from 'next/navigation';
import { type ReactNode, useEffect } from 'react';
import { useMe } from '@/entities/user';
import { ApiError } from '@/shared/api/errors';
import styles from './SessionGate.module.css';

export function SessionGate({ children }: { children: ReactNode }) {
  const { data: user, isLoading, isError, error, refetch } = useMe();
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();

  const isUnauthorized = isError && error instanceof ApiError && error.status === 401;

  useEffect(() => {
    if (isUnauthorized) {
      const encodedNext = encodeURIComponent(pathname || `/${locale}/materials`);
      router.replace(`/${locale}/login?next=${encodedNext}`);
    }
  }, [isUnauthorized, pathname, locale, router]);

  if (isLoading || isUnauthorized) {
    return (
      <div className={styles.gate}>
        <div className={styles.spinner} role="status" aria-label={tCommon('loading')} />
      </div>
    );
  }

  if (isError) {
    const message =
      error instanceof ApiError ? tErrors(error.code) : tErrors('unknown_error');

    return (
      <div className={styles.gate}>
        <div className={styles.errorBox} role="alert">
          <p className={styles.errorText}>{message}</p>
          <button type="button" className={styles.retry} onClick={() => void refetch()}>
            {tCommon('retry')}
          </button>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return <>{children}</>;
}
