"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, qk, unwrap } from "@/shared/api";
import type { components } from "@/shared/api/schema";

type ShareMaterialRequest = components["schemas"]["ShareMaterialRequest"];

export function useShareDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: ShareMaterialRequest) =>
      unwrap(apiClient.POST("/api/v1/materials/share", { body })),
    onSuccess: (_data, { document_id }) =>
      queryClient.invalidateQueries({
        queryKey: qk.document(document_id),
        exact: true,
      }),
  });
}
