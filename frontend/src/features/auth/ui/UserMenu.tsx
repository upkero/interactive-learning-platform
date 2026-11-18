'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useMe } from '@/entities/user/model/useMe';
import { LocaleSwitch } from '@/features/locale/ui/LocaleSwitch';
import { apiClient } from '@/shared/api/client';

export function UserMenu() {
  const { data: user } = useMe();
  const t = useTranslations('common');
  const locale = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();

  const logoutMutation = useMutation({
    mutationFn: async () => {
      await apiClient.POST('/auth/logout');
    },
    onSettled: () => {
      queryClient.clear();
      router.replace(`/${locale}/login`);
    },
  });

  if (!user) return null;

  return (
    <div className="flex items-center gap-4">
      <LocaleSwitch />
      <span className="text-sm text-gray-600">{user.email}</span>
      <button
        type="button"
        onClick={() => logoutMutation.mutate()}
        disabled={logoutMutation.isPending}
        className="rounded-md border px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
      >
        {t('logout')}
      </button>
    </div>
  );
}
