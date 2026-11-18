'use client';

import { useLocale } from 'next-intl';
import { usePathname, useRouter } from 'next/navigation';
import { type ReactNode, useEffect } from 'react';
import { useMe } from '@/entities/user/model/useMe';
import { ApiError } from '@/shared/api/errors';

export function SessionGate({ children }: { children: ReactNode }) {
  const { data: user, isLoading, isError, error } = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();

  useEffect(() => {
    if (isError && error instanceof ApiError && error.status === 401) {
      const encodedNext = encodeURIComponent(pathname || `/${locale}/materials`);
      router.replace(`/${locale}/login?next=${encodedNext}`);
    }
  }, [isError, error, pathname, locale, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return <>{children}</>;
}
