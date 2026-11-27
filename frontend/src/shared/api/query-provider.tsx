"use client";

import {
  QueryClient,
  QueryClientProvider,
  QueryCache,
} from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { type ReactNode, useState, useEffect, useCallback } from "react";
import {
  useNextPathname,
  useNextRouter,
} from "@/shared/i18n/navigation-client";
import { isApiError } from "./errors";

export function QueryProvider({ children }: { children: ReactNode }) {
  const router = useNextRouter();
  const pathname = useNextPathname();
  const locale = useLocale();
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: (failureCount, error) => {
              if (isApiError(error)) {
                // Don't retry on 4xx (except 429) or network_error
                if (
                  error.status >= 400 &&
                  error.status < 500 &&
                  error.status !== 429
                ) {
                  return false;
                }
                // Retry on network_error and 5xx
                if (error.code === "network_error" || error.status >= 500) {
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
            if (isApiError(error) && error.status === 401) {
              window.dispatchEvent(new Event("grasp:unauthorized"));
            }
          },
        }),
      })
  );

  const handleUnauthorized = useCallback((): void => {
    void (async () => {
      try {
        // Dynamically import to avoid circular dependency
        const { apiClient } = await import("./client");
        await apiClient.POST("/api/v1/auth/logout");
      } catch {
        // Ignore logout errors
      } finally {
        queryClient.clear();
        const encodedNext = encodeURIComponent(
          pathname || `/${locale}/materials`
        );
        router.replace(`/${locale}/login?next=${encodedNext}`);
      }
    })();
  }, [locale, pathname, queryClient, router]);

  useEffect(() => {
    // The sign-in and registration pages probe /me before a session exists.
    if (pathname === `/${locale}/login` || pathname === `/${locale}/register`) {
      return;
    }

    window.addEventListener("grasp:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("grasp:unauthorized", handleUnauthorized);
    };
  }, [handleUnauthorized, locale, pathname]);

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
