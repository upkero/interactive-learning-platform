"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { apiClient, unwrap, qk } from "@/shared/api";
import type { components } from "@/shared/api/schema";
import { useQueryClient } from "@tanstack/react-query";

export type GenerateRequest = components["schemas"]["GenerateRequest"];
export type GenerateResponse = components["schemas"]["GenerateResponse"];
export type PlanResponse = components["schemas"]["PlanResponse"];
export type PlannedPartOut = components["schemas"]["PlannedPartOut"];

/**
 * Get the generation plan for selected topics.
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

/**
 * Start document generation with the selected topics and parameters.
 * POST /api/v1/documents/{document_id}/generate
 * Body: { topic_ids: string[], answers: GenerateRequest }
 */
export function useStartGeneration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      documentId,
      topicIds,
      answers,
    }: {
      documentId: string;
      topicIds: string[];
      answers: {
        depth: "overview" | "standard" | "deep";
        goal: "exam" | "understand" | "refresh";
        level: "novice" | "intermediate" | "advanced";
      };
    }) => {
      return unwrap(
        apiClient.POST("/api/v1/documents/{document_id}/generate", {
          params: { path: { document_id: documentId } },
          body: { topic_ids: topicIds, answers },
        })
      );
    },
    onSuccess: (_data, variables) => {
      // Invalidate related queries
      void queryClient.invalidateQueries({
        queryKey: qk.document(variables.documentId),
      });
      void queryClient.invalidateQueries({ queryKey: qk.quota });
      void queryClient.invalidateQueries({ queryKey: qk.materials() });
    },
  });
}
