"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "@/shared/i18n/navigation-client";
import { useMe } from "@/entities/user";
import { LoginForm } from "@/features/auth";

export function RegisterPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: user, isLoading } = useMe();

  useEffect(() => {
    if (!isLoading && user) {
      const nextUrl = searchParams.get("next") || "/materials";
      router.replace(nextUrl);
    }
  }, [user, isLoading, router, searchParams]);

  if (isLoading) {
    return null;
  }

  return <LoginForm mode="register" />;
}
