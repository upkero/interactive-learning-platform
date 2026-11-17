import type { ReactNode } from 'react';
import { QueryProvider } from '@/shared/api/query-provider';

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  return (
    <html lang={locale}>
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
