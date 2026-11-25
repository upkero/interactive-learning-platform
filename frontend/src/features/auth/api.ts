import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, unwrap, qk } from "@/shared/api";
import type { paths } from "@/shared/api/schema";
import {
  useRouter,
  usePathname,
  useSearchParams,
} from "@/shared/i18n/navigation-client";
import { sanitizeNextUrl } from "./model/sanitizeNext";

export type LoginCredentials =
  paths["/api/v1/auth/login"]["post"]["requestBody"]["content"]["application/json"];

export type RegisterCredentials =
  paths["/api/v1/auth/register"]["post"]["requestBody"]["content"]["application/json"];

export async function login(credentials: LoginCredentials) {
  return unwrap(apiClient.POST("/api/v1/auth/login", { body: credentials }));
}

export async function register(credentials: RegisterCredentials) {
  return unwrap(apiClient.POST("/api/v1/auth/register", { body: credentials }));
}

export async function logout() {
  await unwrap(apiClient.POST("/api/v1/auth/logout"));
}

export function useLogin() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();

  return useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      queryClient.setQueryData(qk.me, user);
      const nextUrl = sanitizeNextUrl(searchParams.get("next"), "/materials");
      router.replace(nextUrl);
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();

  return useMutation({
    mutationFn: register,
    onSuccess: (user) => {
      queryClient.setQueryData(qk.me, user);
      const nextUrl = sanitizeNextUrl(searchParams.get("next"), "/materials");
      router.replace(nextUrl);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const locale = pathname.split("/")[1] || "ru";

  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear();
      router.replace(`/${locale}/login`);
    },
  });
}
