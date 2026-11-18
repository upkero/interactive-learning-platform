'use client';

import { useLocale } from 'next-intl';
import { usePathname, useRouter } from 'next/navigation';
import { useTransition } from 'react';

export function LocaleSwitch() {
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
      onClick={toggleLocale}
      disabled={isPending}
      className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-gray-100 disabled:opacity-50 dark:hover:bg-gray-800"
      aria-label="Переключить язык"
    >
      <span className="uppercase font-semibold">{locale}</span>
      <span className="text-xs text-gray-500">
        {locale === 'ru' ? '-> EN' : '-> RU'}
      </span>
    </button>
  );
}