"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient, unwrap, qk } from "@/shared/api";
import type { components } from "@/shared/api/schema";

export const DOCUMENT_QUERY_KEY = (documentId: string) =>
  qk.document(documentId);

export type DocumentOut = components["schemas"]["DocumentOut"];
export type PartSummaryOut = components["schemas"]["PartSummaryOut"];
export type PartOut = components["schemas"]["PartOut"];
export type TopicNodeOut = components["schemas"]["TopicNodeOut"];
export type TopicTreeOut = components["schemas"]["TopicTreeOut"];
export type GenerateRequest = components["schemas"]["GenerateRequest"];
export type GenerateResponse = components["schemas"]["GenerateResponse"];
export type PlanRequest = components["schemas"]["PlanRequest"];
export type PlanResponse = components["schemas"]["PlanResponse"];

export interface DocumentPart {
  id: string;
  index: number;
  title: string;
  status: PartSummaryOut["status"];
  content?: string;
  error_code?: string;
  key_terms?: { term: string; definition: string }[];
  widget_status?: "pending" | "ready" | "fallback";
  quiz_status?: "not_started" | "in_progress" | "completed";
  quiz_score?: { correct: number; total: number };
}

export function useDocument(documentId: string | null) {
  return useQuery({
    queryKey: documentId
      ? DOCUMENT_QUERY_KEY(documentId)
      : ["document", "null"],
    enabled: !!documentId,
    queryFn: async () => {
      if (!documentId) throw new Error("Document ID is required");
      return unwrap(
        apiClient.GET("/api/v1/documents/{document_id}", {
          params: { path: { document_id: documentId } },
        })
      );
    },
  });
}

export function useDocumentTopics(documentId: string | null) {
  return useQuery({
    queryKey: documentId
      ? qk.documentTopics(documentId)
      : ["document", "null", "topics"],
    enabled: !!documentId,
    queryFn: async () => {
      if (!documentId) throw new Error("Document ID is required");
      const data = await unwrap(
        apiClient.GET("/api/v1/documents/{document_id}/topics", {
          params: { path: { document_id: documentId } },
        })
      );
      return data.topics;
    },
  });
}

export function useDocumentParts(documentId: string | null) {
  // Use select to derive parts from the document query (no duplicate request)
  return useQuery({
    queryKey: documentId
      ? qk.documentParts(documentId)
      : ["document", "null", "parts"],
    enabled: !!documentId,
    queryFn: async () => {
      if (!documentId) throw new Error("Document ID is required");
      const document = await unwrap(
        apiClient.GET("/api/v1/documents/{document_id}", {
          params: { path: { document_id: documentId } },
        })
      );
      return document.parts.map((p) => ({
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
    queryKey: partId ? qk.part(partId) : ["part", "null"],
    enabled: !!partId,
    queryFn: async () => {
      if (!partId) throw new Error("Part ID is required");
      return unwrap(
        apiClient.GET("/api/v1/parts/{part_id}", {
          params: { path: { part_id: partId } },
        })
      );
    },
  });
}
