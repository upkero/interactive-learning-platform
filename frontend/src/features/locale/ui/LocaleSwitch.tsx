'use client';

import { useLocale, useTranslations } from 'next-intl';
import { usePathname, useRouter } from 'next/navigation';
import { useTransition } from 'react';
import styles from './LocaleSwitch.module.css';

export function LocaleSwitch() {
  const t = useTranslations('common');
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [isPending, startTransition] = useTransition();

  const toggleLocale = () => {
    const nextLocale = locale === 'ru' ? 'en' : 'ru';

    startTransition(() => {
      const newPath = pathname.replace(new RegExp(`^\\/${locale}`), `/${nextLocale}`);
      router.replace(newPath);
    });
  };

  return (
    <button
      type="button"
      onClick={toggleLocale}
      disabled={isPending}
      className={styles.button}
      aria-label={t('switchLocale')}
      title={t('switchLocale')}
    >
      <span className={styles.current} aria-hidden="true">{locale.toUpperCase()}</span>
      <span className={styles.hint} aria-hidden="true">{locale === 'ru' ? 'EN' : 'RU'}</span>
    </button>
  );
}