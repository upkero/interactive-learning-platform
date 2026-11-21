'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';

export const MATERIALS_QUERY_KEY = ['materials'] as const;

export type MaterialOut = components['schemas']['MaterialOut'];
export type MaterialStatus = MaterialOut['status'];

export function useMaterials(filter: 'mine' | 'shared' = 'mine') {
  return useQuery({
    queryKey: [...MATERIALS_QUERY_KEY, filter],
    queryFn: async () => {
      const { data, response } = await apiClient.GET('/api/v1/me/materials', {
        params: { query: { filter } },
      });
      if (!response.ok || !data) throw new Error('Failed to load materials');
      return data;
    },
  });
}

// DELETE /documents/{document_id} is not in the new schema, using POST with _method override or separate endpoint
// For now, we'll use a no-op mutation that just invalidates queries
export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      // Note: DELETE endpoint not in new schema, this is a placeholder
      console.warn('Delete document not implemented in new API');
      await Promise.resolve();
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: MATERIALS_QUERY_KEY });
    },
  });
}

export function getMaterialRoute(material: MaterialOut): string {
  const { document_id: id, status } = material;
  switch (status) {
    case 'parsing':
    case 'uploaded':
      return `/upload?doc=${id}`;
    case 'parsed':
      return `/documents/${id}/topics`;
    case 'generating':
      return `/documents/${id}/progress`;
    case 'done':
      return `/documents/${id}`;
    case 'failed':
      return ''; // Stay on materials page, show error actions inline
    default:
      return `/documents/${id}`;
  }
}