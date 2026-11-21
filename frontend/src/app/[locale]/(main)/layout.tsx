import type { ReactNode } from 'react';
import { SessionGate } from '@/features/auth';
import { AppShell } from '@/widgets/app-shell';
import styles from './layout.module.css';

export default async function MainLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  return (
    <SessionGate>
      <AppShell locale={locale}>
        <div className={styles.main}>{children}</div>
      </AppShell>
    </SessionGate>
  );
}