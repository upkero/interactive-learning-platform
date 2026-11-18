'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter, useSearchParams } from 'next/navigation';
import { type FormEvent, useState } from 'react';
import { ME_QUERY_KEY } from '@/entities/user/model/useMe';
import { apiClient } from '@/shared/api/client';
import { ApiError } from '@/shared/api/errors';
import { sanitizeNextUrl } from '../model/sanitizeNext';
import { authCredentialsSchema } from '../model/schemas';

export function LoginForm({ mode = 'login' }: { mode?: 'login' | 'register' }) {
  const t = useTranslations('auth');
  const tErrors = useTranslations('errors');
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (credentials: { email: string; password: string }) => {
      const endpoint = mode === 'login' ? '/auth/login' : '/auth/register';
      const { data } = await apiClient.POST(endpoint, { body: credentials });
      return data;
    },
    onSuccess: (user) => {
      queryClient.setQueryData(ME_QUERY_KEY, user);
      const nextUrl = sanitizeNextUrl(searchParams.get('next'), `/${locale}/materials`);
      router.replace(nextUrl);
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setFormError(tErrors(err.code));
      } else {
        setFormError(tErrors('unknown_error'));
      }
    },
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const parsed = authCredentialsSchema.safeParse({ email, password });
    if (!parsed.success) {
      setFormError(parsed.error.errors[0]?.message || tErrors('validation_error'));
      return;
    }

    mutation.mutate(parsed.data);
  };

  return (
    <form onSubmit={handleSubmit} className="mx-auto flex w-full max-w-sm flex-col gap-4 rounded-xl border p-6 shadow-sm">
      <h1 className="text-xl font-bold">
        {mode === 'login' ? t('loginTitle') : t('registerTitle')}
      </h1>

      {formError && (
        <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-600">
          {formError}
        </div>
      )}

      <label className="flex flex-col gap-1 text-sm font-medium">
        {t('emailLabel')}
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="rounded-md border px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm font-medium">
        {t('passwordLabel')}
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          className="rounded-md border px-3 py-2"
        />
      </label>

      <button
        type="submit"
        disabled={mutation.isPending}
        className="rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {mode === 'login' ? t('loginButton') : t('registerButton')}
      </button>
    </form>
  );
}
