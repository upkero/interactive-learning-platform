"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient, unwrap, qk } from "@/shared/api";
import type { components } from "@/shared/api/schema";

export type PartOut = components["schemas"]["PartOut"];
export type PartContentOut = components["schemas"]["PartContentOut"];
export type ChoiceQuiz = components["schemas"]["ChoiceQuiz"];
export type OrderingQuiz = components["schemas"]["OrderingQuiz"];
export type NumericQuiz = components["schemas"]["NumericQuiz"];
export type PendingWidget = components["schemas"]["PendingWidget"];
export type ImageOut = components["schemas"]["ImageOut"];

export type Quiz = ChoiceQuiz | OrderingQuiz | NumericQuiz;

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
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data?.content?.widgets) return false;
      const hasPendingWidget = Object.values(data.content.widgets).some(
        (w): w is PendingWidget => "status" in w && w.status === "pending"
      );
      return hasPendingWidget ? 30_000 : false;
    },
  });
}
