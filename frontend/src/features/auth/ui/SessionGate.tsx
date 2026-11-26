"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter, usePathname } from "@/shared/i18n/navigation-client";
import { type ReactNode, useEffect, useCallback } from "react";
import { useMe } from "@/entities/user";
import { logout } from "../api";
import { useQueryClient } from "@tanstack/react-query";
import { isApiError } from "@/shared/api/errors";
import styles from "./SessionGate.module.css";

export function SessionGate({ children }: { children: ReactNode }) {
  const { data: user, isLoading, isError, error, refetch } = useMe();
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();
  const queryClient = useQueryClient();

  const isUnauthorized =
    isError &&
    error instanceof Error &&
    "status" in error &&
    (error as { status: number }).status === 401;

  const handleUnauthorized = useCallback(async () => {
    try {
      await logout();
    } catch {
      // Ignore logout errors
    }
    queryClient.clear();
    const encodedNext = encodeURIComponent(pathname || `/${locale}/materials`);
    router.replace(`/${locale}/login?next=${encodedNext}`);
  }, [pathname, locale, router, queryClient]);

  useEffect(() => {
    if (isUnauthorized) {
      void handleUnauthorized();
    }
  }, [isUnauthorized, handleUnauthorized]);

  if (isLoading || isUnauthorized) {
    return (
      <div className={styles.gate}>
        <div
          className={styles.spinner}
          role="status"
          aria-label={tCommon("loading")}
        />
      </div>
    );
  }

  if (isError) {
    const message = isApiError(error)
      ? tErrors(error.code)
      : tErrors("unknown_error");

    return (
      <div className={styles.gate}>
        <div className={styles.errorBox} role="alert">
          <p className={styles.errorText}>{message}</p>
          <button
            type="button"
            className={styles.retry}
            onClick={() => void refetch()}
          >
            {tCommon("retry")}
          </button>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return <>{children}</>;
}
