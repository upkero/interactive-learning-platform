'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';

export const DOCUMENT_QUERY_KEY = ['document'] as const;

export type DocumentOut = components['schemas']['DocumentOut'];
export type PartSummaryOut = components['schemas']['PartSummaryOut'];
export type PartOut = components['schemas']['PartOut'];
export type TopicNodeOut = components['schemas']['TopicNodeOut'];
export type TopicTreeOut = components['schemas']['TopicTreeOut'];
export type GenerateRequest = components['schemas']['GenerateRequest'];
export type GenerateResponse = components['schemas']['GenerateResponse'];
export type PlanRequest = components['schemas']['PlanRequest'];
export type PlanResponse = components['schemas']['PlanResponse'];

export interface DocumentPart {
  id: string;
  index: number;
  title: string;
  status: PartSummaryOut['status'];
  content?: string;
  error_code?: string;
  key_terms?: { term: string; definition: string }[];
  widget_status?: 'pending' | 'ready' | 'fallback';
  quiz_status?: 'not_started' | 'in_progress' | 'completed';
  quiz_score?: { correct: number; total: number };
}

export function useDocument(documentId: string | null) {
  return useQuery({
    queryKey: [...DOCUMENT_QUERY_KEY, documentId],
    enabled: !!documentId,
    queryFn: async () => {
      if (!documentId) throw new Error('Document ID is required');
      const { data, response } = await apiClient.GET('/api/v1/documents/{document_id}', {
        params: { path: { document_id: documentId } },
      });
      if (!response.ok || !data) throw new Error('Failed to load document');
      return data;
    },
  });
}

export function useDocumentTopics(documentId: string | null) {
  return useQuery({
    queryKey: [...DOCUMENT_QUERY_KEY, documentId, 'topics'],
    enabled: !!documentId,
    queryFn: async () => {
      if (!documentId) throw new Error('Document ID is required');
      const { data, response } = await apiClient.GET('/api/v1/documents/{document_id}/topics', {
        params: { path: { document_id: documentId } },
      });
      if (!response.ok || !data) throw new Error('Failed to load topics');
      return data.topics;
    },
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (formData: FormData) => {
      const { data, response } = await apiClient.POST('/api/v1/documents', {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        body: formData as any,
      });
      if (!response.ok) throw new Error('Failed to upload document');
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['materials'] });
    },
  });
}

export function useImportDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (url: string) => {
      const { data, response } = await apiClient.POST('/api/v1/documents/import', {
        body: { url },
      });
      if (!response.ok) throw new Error('Failed to import document');
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['materials'] });
    },
  });
}

export function useGenerateDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      documentId,
      body,
    }: {
      documentId: string;
      body: GenerateRequest;
    }) => {
      const { data, response } = await apiClient.POST('/api/v1/documents/{document_id}/generate', {
        params: { path: { document_id: documentId } },
        body,
      });
      if (!response.ok) throw new Error('Failed to start generation');
      return data;
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: [...DOCUMENT_QUERY_KEY, variables.documentId] });
      void queryClient.invalidateQueries({ queryKey: ['me', 'quota'] });
    },
  });
}

export function usePlanDocument() {
  return useMutation({
    mutationFn: async ({
      documentId,
      body,
    }: {
      documentId: string;
      body: PlanRequest;
    }) => {
      const { data, response } = await apiClient.POST('/api/v1/documents/{document_id}/plan', {
        params: { path: { document_id: documentId } },
        body,
      });
      if (!response.ok) throw new Error('Failed to plan generation');
      return data;
    },
  });
}

export function useDocumentParts(documentId: string | null) {
  return useQuery({
    queryKey: [...DOCUMENT_QUERY_KEY, documentId, 'parts'],
    enabled: !!documentId,
    queryFn: async () => {
      if (!documentId) throw new Error('Document ID is required');
      const { data, response } = await apiClient.GET('/api/v1/documents/{document_id}', {
        params: { path: { document_id: documentId } },
      });
      if (!response.ok || !data) throw new Error('Failed to load document');
      return data.parts.map(p => ({
        id: p.id,
        index: p.index,
        title: p.title,
        status: p.status,
      }));
    },
  });
}

export function usePart(partId: string | null) {
  return useQuery({
    queryKey: [...DOCUMENT_QUERY_KEY, 'part', partId],
    enabled: !!partId,
    queryFn: async () => {
      if (!partId) throw new Error('Part ID is required');
      const { data, response } = await apiClient.GET('/api/v1/parts/{part_id}', {
        params: { path: { part_id: partId } },
      });
      if (!response.ok || !data) throw new Error('Failed to load part');
      return data;
    },
  });
}