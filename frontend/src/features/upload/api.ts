"use client";

import { useMutation } from "@tanstack/react-query";
import { apiClient, unwrap, ApiError } from "@/shared/api";
import type { components } from "@/shared/api/schema";
import { useEventStream } from "@/shared/lib/sse/useEventStream";
import { useDocument } from "@/entities/document";

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

interface UseParsingProgressOptions {
  /** Polling interval in ms when SSE is unavailable (default: 2500) */
  pollInterval?: number;
}

interface UseParsingProgressResult {
  /** SSE connection status */
  sseStatus: ReturnType<typeof useEventStream>["status"];
  /** Current document status from polling fallback */
  documentStatus: components["schemas"]["DocumentOut"]["status"] | null;
  /** True while polling or SSE is active */
  isActive: boolean;
}

/**
 * Track parsing progress via SSE with polling fallback.
 * Uses useEventStream for real-time updates and falls back to polling document status
 * when SSE is unavailable or disconnected, while document status is 'uploaded' or 'parsing'.
 */
export function useParsingProgress(
  documentId: string | null,
  options: UseParsingProgressOptions = {}
): UseParsingProgressResult {
  const { pollInterval = 2500 } = options;

  const sseUrl = documentId ? `/api/v1/documents/${documentId}/events` : null;

  const { status: sseStatus } = useEventStream({
    url: sseUrl,
    enabled: !!documentId,
    // Use default event types from useEventStream (stage, part_status, part_ready, document_done, error)
    // No terminalEvents field - not in UseEventStreamOptions
  });

  // Fallback polling: refetch document while status is uploaded or parsing
  const isPollingEnabled =
    !!documentId &&
    (sseStatus === "closed" ||
      sseStatus === "idle" ||
      sseStatus === "reconnecting");

  const { data: document } = useDocument(documentId, {
    enabled: isPollingEnabled,
    refetchInterval: isPollingEnabled ? pollInterval : false,
  });

  const doc: components["schemas"]["DocumentOut"] | undefined = document;
  const documentStatus = doc?.status ?? null;

  // Active if SSE is connecting/open OR polling is active (document is uploaded/parsing)
  const isActive =
    sseStatus === "connecting" ||
    sseStatus === "open" ||
    sseStatus === "reconnecting" ||
    documentStatus === "uploaded" ||
    documentStatus === "parsing";

  return {
    sseStatus,
    documentStatus,
    isActive,
  };
}
