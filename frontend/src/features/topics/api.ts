"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient, unwrap, qk } from "@/shared/api";
import type { components } from "@/shared/api/schema";

export type TopicNodeOut = components["schemas"]["TopicNodeOut"];
export type PlanResponse = components["schemas"]["PlanResponse"];
export type PlannedPartOut = components["schemas"]["PlannedPartOut"];

/**
 * Fetch topics for a document.
 * GET /api/v1/documents/{document_id}/topics
 */
export function useTopics(documentId: string | null) {
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

/**
 * Generate a plan for the selected topics.
 * POST /api/v1/documents/{document_id}/plan
 * Body: { topic_ids: string[] }
 */
export function usePlan(documentId: string | null, topicIds: string[] | null) {
  const sortedTopicIds = topicIds ? [...topicIds].sort() : [];

  return useQuery({
    queryKey: documentId
      ? ["document", documentId, "plan", sortedTopicIds.join(",")]
      : ["document", "null", "plan"],
    enabled: !!documentId && sortedTopicIds.length > 0,
    queryFn: async () => {
      if (!documentId) throw new Error("Document ID is required");
      if (sortedTopicIds.length === 0) throw new Error("No topic IDs provided");
      return unwrap(
        apiClient.POST("/api/v1/documents/{document_id}/plan", {
          params: { path: { document_id: documentId } },
          body: { topic_ids: sortedTopicIds },
        })
      );
    },
  });
}
