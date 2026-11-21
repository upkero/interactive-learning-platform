'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useMe } from '@/entities/user';
import { logout } from '../api';
import styles from './UserMenu.module.css';

export function UserMenu() {
  const { data: user } = useMe();
  const t = useTranslations('common');
  const locale = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear();
      router.replace(`/${locale}/login`);
    },
  });

  if (!user) return null;

  return (
    <div className={styles.menu}>
      <button
        type="button"
        onClick={() => {
          logoutMutation.mutate();
        }}
        disabled={logoutMutation.isPending}
        className={styles.button}
        title={user.email}
        aria-label={t('logout')}
      >
        <span className={styles.icon} aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </span>
        <span className={styles.label}>{t('logout')}</span>
      </button>
    </div>
  );
}