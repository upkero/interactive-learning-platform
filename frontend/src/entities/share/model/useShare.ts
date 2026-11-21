'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';

export const SHARE_QUERY_KEY = ['share'] as const;

export interface ShareInfo {
  document_id: string;
  is_public: boolean;
  public_url?: string;
  shared_with: ShareUser[];
}

export interface ShareUser {
  id: string;
  email: string;
  name?: string;
  granted_at: string;
}

export interface ShareRequest {
  email?: string;
  make_public?: boolean;
}

export interface ShareResponse {
  success: boolean;
  public_url?: string;
  share_info?: ShareInfo;
}

function mapSharedWithOut(users: components['schemas']['SharedWithOut'][]): ShareUser[] {
  return users.map((u) => ({
    id: u.email, // Use email as ID since SharedWithOut doesn't have an ID
    email: u.email,
    name: u.display_name ?? undefined,
    granted_at: u.shared_at,
  }));
}

export function useShareInfo(documentId: string | null) {
  return useQuery({
    queryKey: [...SHARE_QUERY_KEY, documentId],
    enabled: !!documentId,
    queryFn: async () => {
      if (!documentId) throw new Error('Document ID is required');
      const { data, response } = await apiClient.GET('/api/v1/documents/{document_id}', {
        params: { path: { document_id: documentId } },
      });
      if (!response.ok || !data) throw new Error('Failed to load document');
      const doc = data;
      return {
        document_id: documentId,
        is_public: false, // New API doesn't expose public link via document endpoint
        public_url: undefined,
        shared_with: doc.role === 'owner' && doc.shared_with ? mapSharedWithOut(doc.shared_with) : [],
      };
    },
  });
}

export function useShareDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      documentId,
      body,
    }: {
      documentId: string;
      body: ShareRequest;
    }) => {
      if (body.email) {
        const { data, response } = await apiClient.POST('/api/v1/materials/share', {
          body: {
            document_id: documentId,
            email: body.email,
          },
        });
        if (!response.ok || !data) throw new Error('Failed to share document');
        return { success: true };
      }
      // make_public is not supported in new API
      return { success: true };
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: [...SHARE_QUERY_KEY, variables.documentId] });
      void queryClient.invalidateQueries({ queryKey: ['document', variables.documentId] });
    },
  });
}

export function useRevokeShare() {
  return useMutation({
    mutationFn: async () => {
      // New API doesn't have revoke endpoint
      // This is a no-op for compatibility
      console.warn('Revoke share not supported in new API');
      await Promise.resolve();
    },
  });
}

export function useRevokePublicLink() {
  return useMutation({
    mutationFn: async () => {
      // New API doesn't have revoke public link endpoint
      console.warn('Revoke public link not supported in new API');
      await Promise.resolve();
    },
  });
}