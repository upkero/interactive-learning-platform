import { Link, getPathname } from '@/shared/i18n/navigation';
import { getTranslations } from 'next-intl/server';
import { UserMenu } from '@/features/auth';
import { LocaleSwitch } from '@/features/locale';
import { QuotaBadge } from '@/features/materials';
import styles from './AppHeader.module.css';

export async function AppHeader({ locale }: { locale: string }) {
  const tCommon = await getTranslations({ locale, namespace: 'common' });
  const tMaterials = await getTranslations({ locale, namespace: 'materials' });
  const tUpload = await getTranslations({ locale, namespace: 'upload' });

  // Use getPathname for server-side link generation
  const materialsPath = getPathname({ locale, href: '/materials' });
  const uploadPath = getPathname({ locale, href: '/upload' });

  return (
    <header className={styles.header}>
      <Link href={materialsPath} className={styles.brand}>
        {tCommon('appName')}
      </Link>

      <nav className={styles.nav} aria-label={tCommon('appName')}>
        <Link href={materialsPath} className={styles.navLink}>
          {tMaterials('title')}
        </Link>
        <Link href={uploadPath} className={styles.navLink}>
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