'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, unwrap, qk } from '@/shared/api';
import type { components } from '@/shared/api/schema';

export const MATERIALS_QUERY_KEY = qk.materials;

export type MaterialOut = components['schemas']['MaterialOut'];
export type MaterialStatus = MaterialOut['status'];

export function useMaterials(filter: 'mine' | 'shared' = 'mine') {
  return useQuery({
    queryKey: qk.materials(filter),
    queryFn: async () => {
      return unwrap(apiClient.GET('/api/v1/me/materials', {
        params: { query: { filter } },
      }));
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: string) => {
      // Note: DELETE endpoint not in new schema, this is a placeholder
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const _documentId = documentId;
      console.warn('Delete document not implemented in new API');
      await Promise.resolve();
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.materials() });
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