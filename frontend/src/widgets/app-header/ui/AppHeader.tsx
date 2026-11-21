import Link from 'next/link';
import { getTranslations } from 'next-intl/server';
import { UserMenu } from '@/features/auth';
import { LocaleSwitch } from '@/features/locale';
import { QuotaBadge } from '@/features/materials';
import styles from './AppHeader.module.css';

export async function AppHeader({ locale }: { locale: string }) {
  const tCommon = await getTranslations({ locale, namespace: 'common' });
  const tMaterials = await getTranslations({ locale, namespace: 'materials' });
  const tUpload = await getTranslations({ locale, namespace: 'upload' });

  return (
    <header className={styles.header}>
      <Link href={`/${locale}/materials`} className={styles.brand}>
        {tCommon('appName')}
      </Link>

      <nav className={styles.nav} aria-label={tCommon('appName')}>
        <Link href={`/${locale}/materials`} className={styles.navLink}>
          {tMaterials('title')}
        </Link>
        <Link href={`/${locale}/upload`} className={styles.navLink}>
          {tUpload('title')}
        </Link>
      </nav>

      <div className={styles.actions}>
        <QuotaBadge />
        <LocaleSwitch />
        <UserMenu />
      </div>
    </header>
  );
}
