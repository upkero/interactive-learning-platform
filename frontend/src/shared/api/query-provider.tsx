'use client';

import { QueryClient, QueryClientProvider, QueryCache } from '@tanstack/react-query';
import { type ReactNode, useState, useEffect, useCallback } from 'react';
import { useRouter, usePathname } from '@/shared/i18n/navigation-client';
import { isApiError } from './errors';

export function QueryProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: (failureCount, error) => {
              if (isApiError(error)) {
                // Don't retry on 4xx (except 429) or network_error
                if (error.status >= 400 && error.status < 500 && error.status !== 429) {
                  return false;
                }
                // Retry on network_error and 5xx
                if (error.code === 'network_error' || error.status >= 500) {
                  return failureCount < 3;
                }
                return false;
              }
              // Retry on unknown errors (could be network)
              return failureCount < 2;
            },
          },
        },
        queryCache: new QueryCache({
          onError: (error) => {
            // We can't do async redirect here, so we'll handle it in SessionGate
            // and via a custom event
            if (isApiError(error) && error.status === 401) {
              window.dispatchEvent(new CustomEvent('grasp:unauthorized', { detail: { pathname } }));
            }
          },
        }),
      })
  );

  // Handle unauthorized event - separated to avoid async in event listener
  const handleUnauthorized = useCallback((event: Event): void => {
    const customEvent = event as CustomEvent<{ pathname: string }>;
    const { pathname: currentPathname } = customEvent.detail;
    
    // Perform logout and redirect asynchronously
    void (async () => {
      try {
        // Dynamically import to avoid circular dependency
        const { apiClient } = await import('./client');
        await apiClient.POST('/api/v1/auth/logout');
      } catch {
        // Ignore logout errors
      } finally {
        queryClient.clear();
        // Get locale from pathname
        const localeMatch = currentPathname.match(/^\/(ru|en)/);
        const locale = localeMatch ? localeMatch[1] : 'ru';
        const encodedNext = encodeURIComponent(currentPathname || `/${locale}/materials`);
        router.replace(`/${locale}/login?next=${encodedNext}`);
      }
    })();
  }, [queryClient, router]);

  // Listen for unauthorized events and handle redirect
  useEffect(() => {
    window.addEventListener('grasp:unauthorized', handleUnauthorized);
    return () => {
      window.removeEventListener('grasp:unauthorized', handleUnauthorized);
    };
  }, [handleUnauthorized]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}