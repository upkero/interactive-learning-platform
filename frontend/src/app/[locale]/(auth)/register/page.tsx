import { getTranslations } from 'next-intl/server';
import { Suspense } from 'react';
import { RegisterPageClient } from './RegisterPageClient';
import styles from '../auth.module.css';

export default async function RegisterPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'common' });

  return (
    <div className={styles.content}>
      <Suspense fallback={<p className={styles.loading}>{t('loading')}</p>}>
        <RegisterPageClient />
      </Suspense>
    </div>
  );
}