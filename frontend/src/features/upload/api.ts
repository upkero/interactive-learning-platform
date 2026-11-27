"use client";

import { useMutation } from "@tanstack/react-query";
import { apiClient, unwrap, ApiError } from "@/shared/api";
import type { components } from "@/shared/api/schema";

export type UploadProgressCallback = (percent: number) => void;

interface UseUploadDocumentOptions {
  onProgress?: UploadProgressCallback;
}

interface UseUploadDocumentResult {
  mutate: (formData: FormData) => void;
  mutateAsync: (
    formData: FormData
  ) => Promise<components["schemas"]["DocumentCreatedOut"]>;
  isPending: boolean;
  isError: boolean;
  isSuccess: boolean;
  error: Error | null;
  data: components["schemas"]["DocumentCreatedOut"] | undefined;
  reset: () => void;
}

/**
 * Upload a document file using XMLHttpRequest to support progress tracking.
 * POST /api/v1/documents with FormData
 */
export function useUploadDocument(
  options: UseUploadDocumentOptions = {}
): UseUploadDocumentResult {
  const { onProgress } = options;

  return useMutation({
    mutationFn: async (
      formData: FormData
    ): Promise<components["schemas"]["DocumentCreatedOut"]> => {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/v1/documents");

        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable && onProgress) {
            const percent = Math.round((event.loaded / event.total) * 100);
            onProgress(percent);
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const data = JSON.parse(
                xhr.responseText
              ) as components["schemas"]["DocumentCreatedOut"];
              resolve(data);
            } catch {
              reject(
                new ApiError(
                  xhr.status,
                  "unknown_error",
                  "Invalid JSON response"
                )
              );
            }
          } else {
            let payload: unknown = null;
            try {
              payload = JSON.parse(xhr.responseText);
            } catch {
              // No body or invalid JSON
            }
            if (payload) {
              reject(ApiError.fromPayload(xhr.status, payload));
            } else if (xhr.status >= 500) {
              reject(
                new ApiError(
                  xhr.status,
                  "unknown_error",
                  `Server error: ${xhr.statusText}`
                )
              );
            } else {
              reject(
                new ApiError(
                  xhr.status,
                  "internal_server_error",
                  xhr.statusText
                )
              );
            }
          }
        };

        xhr.onerror = () => {
          reject(new ApiError(0, "network_error", "Network error"));
        };

        xhr.ontimeout = () => {
          reject(new ApiError(0, "network_error", "Request timeout"));
        };

        xhr.send(formData);
      });
    },
  });
}

/**
 * Import a Google Docs document.
 * POST /api/v1/documents/import with JSON { url }
 */
export function useImportGdocs() {
  return useMutation({
    mutationFn: async (
      url: string
    ): Promise<components["schemas"]["DocumentCreatedOut"]> => {
      return unwrap(
        apiClient.POST("/api/v1/documents/import", {
          body: { url },
        })
      );
    },
  });
}
