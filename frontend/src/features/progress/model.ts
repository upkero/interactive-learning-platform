"use client";

import type { components } from "@/shared/api/schema";

/**
 * Part status from the API (PartSummaryOut.status)
 * These are the exact values from the backend - do not add "ready"
 */
export type PartStatus = components["schemas"]["PartSummaryOut"]["status"];

/**
 * PartSummaryOut type from the API schema
 */
export type PartSummaryOut = components["schemas"]["PartSummaryOut"];

/**
 * Document status from the API (DocumentOut.status)
 */
export type DocumentStatus = components["schemas"]["DocumentOut"]["status"];

/**
 * A single stage log entry
 */
export interface StageLogEntry {
  eventId: string;
  timestamp: number;
  text: string;
}

/**
 * A part in the progress view
 */
export interface PartInfo {
  id: string;
  index: number;
  title: string;
  status: PartStatus;
  errorCode?: string;
}

/**
 * Key term extracted during generation
 */
export interface KeyTerm {
  term: string;
  definition: string;
}

/**
 * Progress state managed by the reducer
 */
export interface ProgressState {
  /** Hydrated parts from GET /documents/{id} */
  parts: PartInfo[];
  /** Stage log entries (max 200, deduplicated by eventId) */
  stageLog: StageLogEntry[];
  /** Key terms collected from SSE events */
  keyTerms: KeyTerm[];
  /** Current document status */
  documentStatus: DocumentStatus;
  /** ETA in seconds, null if no published parts yet */
  eta: number | null;
  /** Whether connection is lost after 5 reconnect attempts */
  connectionLost: boolean;
  /** Number of reconnection attempts */
  reconnectAttempts: number;
  /** Error code from fatal_error event */
  errorCode: string | null;
  /** Whether we've redirected after document_done */
  hasRedirected: boolean;
}

/**
 * Progress action types
 */
type ProgressAction =
  | {
      type: "HYDRATE";
      payload: {
        document: { parts: PartSummaryOut[]; status: DocumentStatus };
      };
    }
  | {
      type: "STAGE_EVENT";
      payload: { eventId: string; timestamp: number; stage: string };
    }
  | {
      type: "KEY_TERM";
      payload: {
        eventId: string;
        timestamp: number;
        term: string;
        definition: string;
      };
    }
  | { type: "DOCUMENT_DONE"; payload: { eventId: string; timestamp: number } }
  | {
      type: "FATAL_ERROR";
      payload: { eventId: string; timestamp: number; errorCode: string };
    }
  | { type: "RECONNECT_ATTEMPT" }
  | { type: "RECONNECT_SUCCESS" }
  | { type: "RESET" };

/**
 * Maximum number of stage log entries to keep
 */
const MAX_STAGE_LOG_ENTRIES = 200;

/**
 * Maximum reconnection attempts before marking connection as lost
 */
const MAX_RECONNECT_ATTEMPTS = 5;

/**
 * Initialize state from document data (hydration from GET /documents/{id})
 */
export function initializeProgressState(document: {
  parts: PartSummaryOut[];
  status: DocumentStatus;
}): ProgressState {
  const parts: PartInfo[] = document.parts.map((p) => ({
    id: p.id,
    index: p.index,
    title: p.title,
    status: p.status,
  }));

  return {
    parts,
    stageLog: [],
    keyTerms: [],
    documentStatus: document.status,
    eta: calculateEta(parts),
    connectionLost: false,
    reconnectAttempts: 0,
    errorCode: null,
    hasRedirected: false,
  };
}

/**
 * Calculate ETA based on completed parts
 * Returns null if no parts are published yet
 */
function calculateEta(parts: PartInfo[]): number | null {
  const publishedParts = parts.filter((p) => p.status === "published");
  const remainingParts = parts.filter(
    (p) => p.status !== "published" && p.status !== "failed"
  );

  if (publishedParts.length === 0 || remainingParts.length === 0) {
    return null;
  }

  // The document summary does not include stage durations.
  return null;
}

/**
 * Calculate ETA from part durations
 */
export function calculateEtaFromDurations(
  completedDurations: number[],
  remainingCount: number
): number | null {
  if (completedDurations.length === 0 || remainingCount === 0) {
    return null;
  }

  const avgDuration =
    completedDurations.reduce((a, b) => a + b, 0) / completedDurations.length;
  return Math.ceil(avgDuration * remainingCount);
}

/**
 * Progress reducer - pure function with no side effects
 */
export function progressReducer(
  state: ProgressState,
  action: ProgressAction
): ProgressState {
  switch (action.type) {
    case "HYDRATE": {
      const { parts, documentStatus, eta } = initializeProgressState(
        action.payload.document
      );
      return { ...state, parts, documentStatus, eta };
    }

    case "STAGE_EVENT": {
      // Deduplicate by eventId
      const exists = state.stageLog.some(
        (entry) => entry.eventId === action.payload.eventId
      );
      if (exists) {
        return state;
      }

      const newEntry: StageLogEntry = {
        eventId: action.payload.eventId,
        timestamp: action.payload.timestamp,
        text: action.payload.stage,
      };

      // Add new entry at the end (newest last), trim to MAX_STAGE_LOG_ENTRIES
      const newStageLog = [...state.stageLog, newEntry].slice(
        -MAX_STAGE_LOG_ENTRIES
      );

      return {
        ...state,
        stageLog: newStageLog,
      };
    }

    case "KEY_TERM": {
      // Deduplicate by eventId (though key_term events may not have unique IDs)
      const newTerm: KeyTerm = {
        term: action.payload.term,
        definition: action.payload.definition,
      };

      // Avoid duplicates by term
      const termExists = state.keyTerms.some((kt) => kt.term === newTerm.term);
      if (termExists) {
        return state;
      }

      return {
        ...state,
        keyTerms: [...state.keyTerms, newTerm],
      };
    }

    case "DOCUMENT_DONE": {
      // Deduplicate by eventId
      const exists = state.stageLog.some(
        (entry) => entry.eventId === action.payload.eventId
      );
      if (exists) {
        return state;
      }

      const newEntry: StageLogEntry = {
        eventId: action.payload.eventId,
        timestamp: action.payload.timestamp,
        text: "document_done",
      };

      const newStageLog = [...state.stageLog, newEntry].slice(
        -MAX_STAGE_LOG_ENTRIES
      );

      return {
        ...state,
        stageLog: newStageLog,
        documentStatus: "done",
        hasRedirected: true,
        eta: null, // No ETA needed, generation complete
      };
    }

    case "FATAL_ERROR": {
      const exists = state.stageLog.some(
        (entry) => entry.eventId === action.payload.eventId
      );
      if (exists) {
        return state;
      }

      const newEntry: StageLogEntry = {
        eventId: action.payload.eventId,
        timestamp: action.payload.timestamp,
        text: `fatal_error: ${action.payload.errorCode}`,
      };

      const newStageLog = [...state.stageLog, newEntry].slice(
        -MAX_STAGE_LOG_ENTRIES
      );

      return {
        ...state,
        stageLog: newStageLog,
        documentStatus: "failed",
        errorCode: action.payload.errorCode,
        eta: null,
      };
    }

    case "RECONNECT_ATTEMPT": {
      const newAttempts = state.reconnectAttempts + 1;
      return {
        ...state,
        reconnectAttempts: newAttempts,
        connectionLost: newAttempts >= MAX_RECONNECT_ATTEMPTS,
      };
    }

    case "RECONNECT_SUCCESS": {
      return {
        ...state,
        reconnectAttempts: 0,
        connectionLost: false,
      };
    }

    case "RESET": {
      return initializeProgressState({
        parts: [],
        status: "generating",
      });
    }

    default:
      return state;
  }
}

/**
 * Create action creators for use with dispatch
 */
export const progressActions = {
  hydrate: (document: { parts: PartSummaryOut[]; status: DocumentStatus }) => ({
    type: "HYDRATE" as const,
    payload: { document },
  }),
  stageEvent: (eventId: string, timestamp: number, stage: string) => ({
    type: "STAGE_EVENT" as const,
    payload: { eventId, timestamp, stage },
  }),
  keyTerm: (
    eventId: string,
    timestamp: number,
    term: string,
    definition: string
  ) => ({
    type: "KEY_TERM" as const,
    payload: { eventId, timestamp, term, definition },
  }),
  documentDone: (eventId: string, timestamp: number) => ({
    type: "DOCUMENT_DONE" as const,
    payload: { eventId, timestamp },
  }),
  fatalError: (eventId: string, timestamp: number, errorCode: string) => ({
    type: "FATAL_ERROR" as const,
    payload: { eventId, timestamp, errorCode },
  }),
  reconnectAttempt: () => ({ type: "RECONNECT_ATTEMPT" as const }),
  reconnectSuccess: () => ({ type: "RECONNECT_SUCCESS" as const }),
  reset: () => ({ type: "RESET" as const }),
};
