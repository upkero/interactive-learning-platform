"use client";

import { useCallback, useEffect, useMemo, useReducer } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import {
  useEventStream,
  type SseEventMessage,
} from "@/shared/lib/sse/useEventStream";
import { useDocument, DOCUMENT_QUERY_KEY } from "@/entities/document";
import { qk } from "@/shared/api";
import {
  initializeProgressState,
  progressReducer,
  progressActions,
  type DocumentStatus,
} from "./model";

const emptyDocument = { parts: [], status: "generating" as DocumentStatus };
const stageEventData = z.object({ stage: z.string() });
const errorEventData = z.object({ error_code: z.string() });

export function useProgressState(documentId: string) {
  const queryClient = useQueryClient();
  const documentQuery = useDocument(documentId);
  const document = documentQuery.data;
  const [streamState, dispatch] = useReducer(
    progressReducer,
    emptyDocument,
    initializeProgressState
  );

  const state = useMemo(
    () =>
      document
        ? progressReducer(streamState, progressActions.hydrate(document))
        : streamState,
    [document, streamState]
  );

  const handleEvent = useCallback(
    ({ id, event, data }: SseEventMessage) => {
      const timestamp = Date.now();
      const eventId = id ?? `${event}${String(timestamp)}`;

      switch (event) {
        case "stage": {
          const result = stageEventData.safeParse(data);
          if (result.success) {
            dispatch(
              progressActions.stageEvent(eventId, timestamp, result.data.stage)
            );
          }
          return;
        }
        case "part_status":
        case "part_ready":
          break;
        case "document_done":
          dispatch(progressActions.documentDone(eventId, timestamp));
          void queryClient.invalidateQueries({ queryKey: qk.materials() });
          break;
        case "error": {
          const result = errorEventData.safeParse(data);
          if (result.success) {
            dispatch(
              progressActions.fatalError(
                eventId,
                timestamp,
                result.data.error_code
              )
            );
          }
          void queryClient.invalidateQueries({ queryKey: qk.materials() });
          break;
        }
        default:
          return;
      }

      // Progress events have a part_id and optional stage. The document query
      // supplies the current part summaries and the final document status.
      void queryClient.invalidateQueries({
        queryKey: DOCUMENT_QUERY_KEY(documentId),
      });
    },
    [documentId, queryClient]
  );

  const { status: sseStatus } = useEventStream({
    url: `/api/v1/documents/${documentId}/events`,
    enabled:
      document?.status === "generating" &&
      !state.hasRedirected &&
      !state.errorCode,
    onEvent: handleEvent,
  });

  useEffect(() => {
    if (sseStatus === "reconnecting") {
      dispatch(progressActions.reconnectAttempt());
    } else if (sseStatus === "open") {
      dispatch(progressActions.reconnectSuccess());
    }
  }, [sseStatus]);

  return { state, dispatch, sseStatus, documentQuery };
}
