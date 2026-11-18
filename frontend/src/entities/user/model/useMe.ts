'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/shared/api/client';

export const ME_QUERY_KEY = ['me'] as const;
export const QUOTA_QUERY_KEY = ['me', 'quota'] as const;

export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      const { data } = await apiClient.GET('/me');
      if (!data) throw new Error('Failed to load user profile');
      return data;
    },
  });
}

export function useQuota() {
  return useQuery({
    queryKey: QUOTA_QUERY_KEY,
    queryFn: async () => {
      const { data } = await apiClient.GET('/me/quota');
      if (!data) throw new Error('Failed to load quota');
      return data;
    },
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: { notify_by_email?: boolean; locale?: 'ru' | 'en' }) => {
      const { data } = await apiClient.PATCH('/me', { body });
      return data;
    },
    onSuccess: (updatedUser) => {
      if (updatedUser) {
        queryClient.setQueryData(ME_QUERY_KEY, updatedUser);
      }
    },
  });
}
