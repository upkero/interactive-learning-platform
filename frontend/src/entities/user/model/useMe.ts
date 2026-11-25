'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, unwrap, qk } from '@/shared/api';
import type { components } from '@/shared/api/schema';

export const ME_QUERY_KEY = qk.me;
export const QUOTA_QUERY_KEY = qk.quota;

export type MeOut = components['schemas']['AuthUserOut'];
export type QuotaOut = components['schemas']['QuotaOut'];

export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      return unwrap(apiClient.GET('/api/v1/me'));
    },
  });
}

export function useQuota() {
  return useQuery({
    queryKey: QUOTA_QUERY_KEY,
    queryFn: async () => {
      return unwrap(apiClient.GET('/api/v1/me/quota'));
    },
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: components['schemas']['MePatch']) => {
      return unwrap(apiClient.PATCH('/api/v1/me', { body }));
    },
    onSuccess: (updatedUser) => {
      queryClient.setQueryData(ME_QUERY_KEY, updatedUser);
    },
  });
}