import { describe, it, expect } from "vitest";
import {
  progressReducer,
  progressActions,
  initializeProgressState,
  calculateEtaFromDurations,
  type ProgressState,
  type PartSummaryOut,
  type DocumentStatus,
} from "./model";

describe("progressReducer", () => {
  const createMockPart = (
    overrides: Partial<PartSummaryOut> = {}
  ): PartSummaryOut => ({
    id: "part-1",
    index: 1,
    title: "Test Part",
    status: "queued",
    ...overrides,
  });

  const createMockDocument = (
    parts: PartSummaryOut[] = [],
    status: DocumentStatus = "generating"
  ) => ({
    parts,
    status,
  });

  describe("initializeProgressState", () => {
    it("should create initial state from document with parts", () => {
      const parts = [
        createMockPart({ id: "part-1", status: "queued" }),
        createMockPart({ id: "part-2", status: "main_pass" }),
      ];
      const document = createMockDocument(parts);

      const state = initializeProgressState(document);

      expect(state.parts).toHaveLength(2);
      expect(state.parts[0].id).toBe("part-1");
      expect(state.parts[0].status).toBe("queued");
      expect(state.parts[1].status).toBe("main_pass");
      expect(state.stageLog).toHaveLength(0);
      expect(state.keyTerms).toHaveLength(0);
      expect(state.documentStatus).toBe("generating");
      expect(state.eta).toBeNull(); // No published parts yet
      expect(state.connectionLost).toBe(false);
      expect(state.reconnectAttempts).toBe(0);
      expect(state.errorCode).toBeNull();
      expect(state.hasRedirected).toBe(false);
    });

    it("should handle empty parts array", () => {
      const document = createMockDocument([]);

      const state = initializeProgressState(document);

      expect(state.parts).toHaveLength(0);
      expect(state.eta).toBeNull();
    });
  });

  describe("HYDRATE action", () => {
    it("should refresh the document snapshot and preserve stream state", () => {
      const initialState: ProgressState = {
        parts: [],
        stageLog: [{ eventId: "old", timestamp: 1000, text: "old" }],
        keyTerms: [{ term: "old", definition: "old" }],
        documentStatus: "uploaded",
        eta: 100,
        connectionLost: true,
        reconnectAttempts: 5,
        errorCode: "some_error",
        hasRedirected: true,
      };

      const parts = [createMockPart({ id: "part-1", status: "published" })];
      const action = progressActions.hydrate(
        createMockDocument(parts, "generating")
      );
      const newState = progressReducer(initialState, action);

      expect(newState.parts).toHaveLength(1);
      expect(newState.parts[0].status).toBe("published");
      expect(newState.documentStatus).toBe("generating");
      expect(newState.stageLog).toEqual(initialState.stageLog);
      expect(newState.keyTerms).toEqual(initialState.keyTerms);
      expect(newState.eta).toBeNull();
      expect(newState.connectionLost).toBe(true);
      expect(newState.reconnectAttempts).toBe(5);
      expect(newState.errorCode).toBe("some_error");
      expect(newState.hasRedirected).toBe(true);
    });
  });

  describe("STAGE_EVENT action", () => {
    it("should add stage event to log", () => {
      const initialState = initializeProgressState(createMockDocument());
      const action = progressActions.stageEvent(
        "evt-1",
        1000,
        "stage: parsing"
      );
      const newState = progressReducer(initialState, action);

      expect(newState.stageLog).toHaveLength(1);
      expect(newState.stageLog[0].eventId).toBe("evt-1");
      expect(newState.stageLog[0].text).toBe("stage: parsing");
      expect(newState.stageLog[0].timestamp).toBe(1000);
    });

    it("should deduplicate by eventId", () => {
      let state = initializeProgressState(createMockDocument());
      state = progressReducer(
        state,
        progressActions.stageEvent("evt-1", 1000, "stage 1")
      );
      state = progressReducer(
        state,
        progressActions.stageEvent("evt-1", 2000, "stage 2")
      );

      expect(state.stageLog).toHaveLength(1);
      expect(state.stageLog[0].text).toBe("stage 1"); // First one kept
    });

    it("should limit log to 200 entries", () => {
      let state = initializeProgressState(createMockDocument());

      for (let i = 0; i < 250; i++) {
        const eventId = `evt-${String(i)}`;
        const stageText = `stage ${String(i)}`;
        state = progressReducer(
          state,
          progressActions.stageEvent(eventId, i, stageText)
        );
      }

      expect(state.stageLog).toHaveLength(200);
      expect(state.stageLog[0].eventId).toBe("evt-50"); // First 50 trimmed
      expect(state.stageLog[199].eventId).toBe("evt-249");
    });
  });

  describe("KEY_TERM action", () => {
    it("should add key term", () => {
      const initialState = initializeProgressState(createMockDocument());
      const action = progressActions.keyTerm(
        "evt-1",
        1000,
        "term1",
        "definition1"
      );
      const newState = progressReducer(initialState, action);

      expect(newState.keyTerms).toHaveLength(1);
      expect(newState.keyTerms[0].term).toBe("term1");
      expect(newState.keyTerms[0].definition).toBe("definition1");
    });

    it("should deduplicate by term", () => {
      let state = initializeProgressState(createMockDocument());
      state = progressReducer(
        state,
        progressActions.keyTerm("evt-1", 1000, "term1", "definition1")
      );
      state = progressReducer(
        state,
        progressActions.keyTerm("evt-2", 2000, "term1", "definition2")
      );

      expect(state.keyTerms).toHaveLength(1);
      expect(state.keyTerms[0].definition).toBe("definition1"); // First one kept
    });
  });

  describe("DOCUMENT_DONE action", () => {
    it("should mark document as done and set hasRedirected", () => {
      const initialState = initializeProgressState(createMockDocument());
      const action = progressActions.documentDone("evt-done", 1000);
      const newState = progressReducer(initialState, action);

      expect(newState.documentStatus).toBe("done");
      expect(newState.hasRedirected).toBe(true);
      expect(newState.eta).toBeNull();
      expect(newState.stageLog).toHaveLength(1);
      expect(newState.stageLog[0].text).toBe("document_done");
    });

    it("should deduplicate by eventId", () => {
      let state = initializeProgressState(createMockDocument());
      state = progressReducer(
        state,
        progressActions.documentDone("evt-done", 1000)
      );
      state = progressReducer(
        state,
        progressActions.documentDone("evt-done", 2000)
      );

      expect(state.stageLog).toHaveLength(1);
    });
  });

  describe("FATAL_ERROR action", () => {
    it("should set error code and mark document as failed", () => {
      const initialState = initializeProgressState(createMockDocument());
      const action = progressActions.fatalError(
        "evt-error",
        1000,
        "quota_exceeded"
      );
      const newState = progressReducer(initialState, action);

      expect(newState.documentStatus).toBe("failed");
      expect(newState.errorCode).toBe("quota_exceeded");
      expect(newState.eta).toBeNull();
      expect(newState.stageLog).toHaveLength(1);
      expect(newState.stageLog[0].text).toBe("fatal_error: quota_exceeded");
    });

    it("should deduplicate by eventId", () => {
      let state = initializeProgressState(createMockDocument());
      state = progressReducer(
        state,
        progressActions.fatalError("evt-error", 1000, "error1")
      );
      state = progressReducer(
        state,
        progressActions.fatalError("evt-error", 2000, "error2")
      );

      expect(state.stageLog).toHaveLength(1);
    });
  });

  describe("RECONNECT_ATTEMPT action", () => {
    it("should increment reconnect attempts", () => {
      const initialState = initializeProgressState(createMockDocument());
      const state = progressReducer(
        initialState,
        progressActions.reconnectAttempt()
      );

      expect(state.reconnectAttempts).toBe(1);
      expect(state.connectionLost).toBe(false);
    });

    it("should set connectionLost after 5 attempts", () => {
      let state = initializeProgressState(createMockDocument());

      for (let i = 0; i < 5; i++) {
        state = progressReducer(state, progressActions.reconnectAttempt());
      }

      expect(state.reconnectAttempts).toBe(5);
      expect(state.connectionLost).toBe(true);
    });
  });

  describe("RECONNECT_SUCCESS action", () => {
    it("should reset reconnect attempts and connectionLost", () => {
      let state = initializeProgressState(createMockDocument());

      // Simulate 5 failed attempts
      for (let i = 0; i < 5; i++) {
        state = progressReducer(state, progressActions.reconnectAttempt());
      }
      expect(state.connectionLost).toBe(true);

      // Successful reconnect
      state = progressReducer(state, progressActions.reconnectSuccess());

      expect(state.reconnectAttempts).toBe(0);
      expect(state.connectionLost).toBe(false);
    });
  });

  describe("RESET action", () => {
    it("should reset to initial state", () => {
      let state = initializeProgressState(
        createMockDocument([
          createMockPart({ id: "part-1", status: "published" }),
        ])
      );

      state = progressReducer(
        state,
        progressActions.stageEvent("evt-1", 1000, "stage")
      );
      state = progressReducer(state, progressActions.reconnectAttempt());
      state = progressReducer(state, progressActions.reconnectAttempt());

      state = progressReducer(state, progressActions.reset());

      expect(state.parts).toHaveLength(0);
      expect(state.stageLog).toHaveLength(0);
      expect(state.keyTerms).toHaveLength(0);
      expect(state.documentStatus).toBe("generating");
      expect(state.reconnectAttempts).toBe(0);
      expect(state.connectionLost).toBe(false);
      expect(state.errorCode).toBeNull();
      expect(state.hasRedirected).toBe(false);
    });
  });
});

describe("calculateEtaFromDurations", () => {
  it("should return null when no completed durations", () => {
    expect(calculateEtaFromDurations([], 5)).toBeNull();
  });

  it("should return null when no remaining parts", () => {
    expect(calculateEtaFromDurations([10, 20, 30], 0)).toBeNull();
  });

  it("should calculate ETA as average * remaining", () => {
    // Average of [10, 20, 30] = 20, remaining = 2, ETA = 40
    expect(calculateEtaFromDurations([10, 20, 30], 2)).toBe(40);
  });

  it("should ceil the result", () => {
    // Average of [10, 10] = 10, remaining = 3, ETA = 30
    expect(calculateEtaFromDurations([10, 10], 3)).toBe(30);
  });
});
