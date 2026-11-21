'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { UserMenu } from '@/features/auth';
import { LocaleSwitch } from '@/features/locale';
import { QuotaBadge } from '@/features/materials';
import styles from './AppShell.module.css';

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

export function AppShell({
  children,
  locale,
}: {
  children: React.ReactNode;
  locale: string;
}) {
  const pathname = usePathname();
  const tCommon = useTranslations('common');
  const tMaterials = useTranslations('materials');
  const tUpload = useTranslations('upload');

  const navItems: NavItem[] = [
    {
      href: `/${locale}/materials`,
      label: tMaterials('title'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      ),
    },
    {
      href: `/${locale}/upload`,
      label: tUpload('title'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="23 4 23 10 17 10" />
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
        </svg>
      ),
    },
  ];

  return (
    <div className={styles.shell}>
      {/* Icon Rail - Left side */}
      <aside className={styles.iconRail} aria-label={tCommon('navigation')}>
        <div className={styles.railTop}>
          <Link href={`/${locale}/materials`} className={styles.brand} aria-label={tCommon('appName')}>
            <span className={styles.brandMark} aria-hidden="true">
              <svg width="28" height="28" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="32" height="32" rx="6" fill="currentColor" />
                <path d="M8 16L14 22L24 10" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span className={styles.brandText}>{tCommon('appName')}</span>
          </Link>
        </div>

        <nav className={styles.nav} aria-label={tCommon('mainNavigation')}>
          <ul className={styles.navList}>
            {navItems.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`${styles.navLink} ${pathname === item.href ? styles.active : ''}`}
                  aria-current={pathname === item.href ? 'page' : undefined}
                >
                  <span className={styles.navIcon} aria-hidden="true">{item.icon}</span>
                  <span className={styles.navLabel}>{item.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className={styles.railBottom}>
          <LocaleSwitch />
          <UserMenu />
        </div>
      </aside>

      {/* Main Content Area - Right side */}
      <main className={styles.main}>
        {/* Top bar with quota badge */}
        <div className={styles.topBar}>
          <QuotaBadge />
        </div>

        {/* Content container */}
        <div className={styles.content}>{children}</div>
      </main>

      {/* Mobile bottom navigation */}
      <nav className={styles.mobileNav} aria-label={tCommon('mobileNavigation')}>
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`${styles.mobileNavItem} ${pathname === item.href ? styles.active : ''}`}
            aria-current={pathname === item.href ? 'page' : undefined}
          >
            <span className={styles.mobileNavIcon} aria-hidden="true">{item.icon}</span>
            <span className={styles.mobileNavLabel}>{item.label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}