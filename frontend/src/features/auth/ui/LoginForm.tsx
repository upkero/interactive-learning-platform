'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { type SyntheticEvent, useState } from 'react';
import { ME_QUERY_KEY } from '@/entities/user';
import { ApiError } from '@/shared/api/errors';
import { login, register, type LoginCredentials, type RegisterCredentials } from '../api';
import { sanitizeNextUrl } from '../model/sanitizeNext';
import { authCredentialsSchema } from '../model/schemas';
import styles from './LoginForm.module.css';

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
    mutationFn: async (credentials: LoginCredentials | RegisterCredentials) => {
      return mode === 'login' ? login(credentials) : register(credentials);
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

  const handleSubmit = (e: SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormError(null);

    const parsed = authCredentialsSchema.safeParse({ email, password });
    if (!parsed.success) {
      const issue = parsed.error.errors[0]?.message;
      setFormError(issue ? tErrors(issue) : tErrors('validation_error'));
      return;
    }

    mutation.mutate(parsed.data);
  };

  return (
    <form onSubmit={handleSubmit} className={styles.form} noValidate>
      <h1 className={styles.title}>
        {mode === 'login' ? t('loginTitle') : t('registerTitle')}
      </h1>

      {formError && (
        <div role="alert" className={styles.error}>
          {formError}
        </div>
      )}

      <div className={styles.field}>
        <label htmlFor="email" className={styles.label}>
          {t('emailLabel')}
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
          }}
          required
          autoComplete="email"
          className={styles.input}
          disabled={mutation.isPending}
        />
      </div>

      <div className={styles.field}>
        <label htmlFor="password" className={styles.label}>
          {t('passwordLabel')}
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
          }}
          required
          minLength={8}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          className={styles.input}
          disabled={mutation.isPending}
        />
      </div>

      <button type="submit" disabled={mutation.isPending} className={styles.submit}>
        {mode === 'login' ? t('loginButton') : t('registerButton')}
        {mutation.isPending && <span className={styles.spinner} aria-hidden="true" />}
      </button>

      <p className={styles.switch}>
        {mode === 'login' ? t('noAccount') : t('hasAccount')}{' '}
        <Link
          href={mode === 'login' ? `/${locale}/register` : `/${locale}/login`}
          className={styles.switchLink}
        >
          {mode === 'login' ? t('registerButton') : t('loginButton')}
        </Link>
      </p>
    </form>
  );
}