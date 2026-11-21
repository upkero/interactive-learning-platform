'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';

export const ME_QUERY_KEY = ['me'] as const;
export const QUOTA_QUERY_KEY = ['me', 'quota'] as const;

export type MeOut = components['schemas']['MeOut'];
export type QuotaOut = components['schemas']['QuotaOut'];

export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      const { data, response } = await apiClient.GET('/api/v1/me');
      if (!response.ok || !data) throw new Error('Failed to load user profile');
      return data;
    },
  });
}

export function useQuota() {
  return useQuery({
    queryKey: QUOTA_QUERY_KEY,
    queryFn: async () => {
      const { data, response } = await apiClient.GET('/api/v1/me/quota');
      if (!response.ok || !data) throw new Error('Failed to load quota');
      return data;
    },
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: components['schemas']['MePatch']) => {
      const { data, response } = await apiClient.PATCH('/api/v1/me', { body });
      if (!response.ok || !data) throw new Error('Failed to update preferences');
      return data;
    },
    onSuccess: (updatedUser) => {
      queryClient.setQueryData(ME_QUERY_KEY, updatedUser);
    },
  });
}
