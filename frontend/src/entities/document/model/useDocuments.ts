"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient, unwrap, qk } from "@/shared/api";
import type { components } from "@/shared/api/schema";

export const MATERIALS_QUERY_KEY = qk.materials;

export type MaterialOut = components["schemas"]["MaterialOut"];
export type MaterialStatus = MaterialOut["status"];

export function useMaterials(filter: "mine" | "shared" = "mine") {
  return useQuery({
    queryKey: qk.materials(filter),
    queryFn: async () => {
      return unwrap(
        apiClient.GET("/api/v1/me/materials", {
          params: { query: { filter } },
        })
      );
    },
  });
}

export function getMaterialRoute(material: MaterialOut): string {
  const { document_id: id, status } = material;

  switch (status) {
    case "uploaded":
    case "parsing":
    case "failed":
      return `/upload?document=${id}`;
    case "parsed":
      return `/documents/${id}/topics`;
    case "generating":
      return `/documents/${id}/progress`;
    case "done":
      // Document view removed, redirect to materials list
      return `/materials`;
    default:
      return `/materials`;
  }
}
