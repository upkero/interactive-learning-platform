"use client";

import { useEffect } from "react";
import { useNextRouter } from "@/shared/i18n/navigation-client";
import { useMe } from "@/entities/user";
import { LoginForm, useAuthReturnUrl } from "@/features/auth";

export function LoginPageClient() {
  const router = useNextRouter();
  const nextUrl = useAuthReturnUrl();
  const { data: user, isLoading } = useMe();

  useEffect(() => {
    if (!isLoading && user) {
      router.replace(nextUrl);
    }
  }, [user, isLoading, router, nextUrl]);

  if (isLoading) {
    return null;
  }

  return <LoginForm mode="login" />;
}
