"use client";

import { useCallback, useEffect, useMemo, useReducer } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useEventStream,
  type SseEventMessage,
} from "@/shared/lib/sse/useEventStream";
import { useDocument, DOCUMENT_QUERY_KEY } from "@/entities/document";
import { qk } from "@/shared/api";
import {
  progressReducer,
  progressActions,
  type ProgressState,
  type PartSummaryOut,
  type PartStatusEventData,
} from "./model";

/**
 * Hook that combines useReducer with SSE for complete progress management
 * This is the main hook components should use
 */
export function useProgressState(documentId: string) {
  const queryClient = useQueryClient();

  // Fetch initial document for hydration
  const documentQuery = useDocument(documentId);

  // Initialize state from document or empty
  const initialState = useMemo(() => {
    if (documentQuery.data) {
      return progressReducer(
        undefined as unknown as ProgressState,
        progressActions.hydrate({
          parts: documentQuery.data.parts,
          status: documentQuery.data.status,
        })
      );
    }
    return progressReducer(
      undefined as unknown as ProgressState,
      progressActions.hydrate({
        parts: [],
        status: "generating",
      })
    );
  }, [documentQuery.data]);

  // Use reducer for state management
  const [state, dispatch] = useReducer(
    progressReducer,
    initialState,
    (init) => init
  );

  // SSE event handler with dispatch
  const handleEvent = useCallback(
    (message: SseEventMessage) => {
      const { id: eventId, event, data } = message;
      const timestamp = Date.now();
      const eId = eventId ?? `${event}${String(timestamp)}`;

      switch (event) {
        case "stage": {
          const stageData = data as { stage: string; document_id: string };
          dispatch(progressActions.stageEvent(eId, timestamp, stageData.stage));
          break;
        }
        case "part_status": {
          const partData = data as PartStatusEventData;
          dispatch(progressActions.partStatus(eId, timestamp, partData));
          break;
        }
        case "part_ready": {
          // part_ready is a legacy event, treat as part_status with published
          const partData = data as PartSummaryOut;
          dispatch(
            progressActions.partStatus(eId, timestamp, {
              ...partData,
              status: "published",
            })
          );
          break;
        }
        case "key_term": {
          const termData = data as { term: string; definition: string };
          dispatch(
            progressActions.keyTerm(
              eId,
              timestamp,
              termData.term,
              termData.definition
            )
          );
          break;
        }
        case "document_done": {
          dispatch(progressActions.documentDone(eId, timestamp));
          // Invalidate document and materials queries
          void queryClient.invalidateQueries({
            queryKey: DOCUMENT_QUERY_KEY(documentId),
          });
          void queryClient.invalidateQueries({ queryKey: qk.materials() });
          break;
        }
        case "error": {
          const errorData = data as { error_code: string; message: string };
          dispatch(
            progressActions.fatalError(eId, timestamp, errorData.error_code)
          );
          void queryClient.invalidateQueries({
            queryKey: DOCUMENT_QUERY_KEY(documentId),
          });
          void queryClient.invalidateQueries({ queryKey: qk.materials() });
          break;
        }
      }
    },
    [documentId, queryClient]
  );

  // Track SSE connection status for reconnection attempts
  const sseUrl = `/api/v1/documents/${documentId}/events`;
  const isGenerating = documentQuery.data?.status === "generating";

  const { status: sseStatus } = useEventStream({
    url: sseUrl,
    enabled: isGenerating && !state.hasRedirected && !state.errorCode,
    eventTypes: [
      "stage",
      "part_status",
      "part_ready",
      "document_done",
      "error",
    ],
    onEvent: handleEvent,
  });

  // Track reconnection attempts
  useEffect(() => {
    if (sseStatus === "reconnecting") {
      dispatch(progressActions.reconnectAttempt());
    } else if (sseStatus === "open") {
      dispatch(progressActions.reconnectSuccess());
    }
  }, [sseStatus]); // dispatch is stable from useReducer

  // Refetch document when SSE reconnects after being closed (to catch up)
  useEffect(() => {
    if (sseStatus === "open" && documentQuery.data?.status === "generating") {
      // Could refetch here if needed, but SSE with last_event_id should handle catch-up
    }
  }, [sseStatus, documentQuery.data?.status]);

  return {
    state,
    dispatch,
    sseStatus,
    documentQuery,
  };
}
