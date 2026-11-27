"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, unwrap, qk } from "@/shared/api";
import type { components } from "@/shared/api/schema";

export function useShareMaterial() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      documentId,
      email,
    }: {
      documentId: string;
      email: string;
    }) => {
      return unwrap(
        apiClient.POST("/api/v1/materials/share", {
          body: {
            document_id: documentId,
            email,
          },
        })
      );
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: qk.document(variables.documentId),
      });
    },
  });
}

export type SharedWithOut = components["schemas"]["SharedWithOut"];
