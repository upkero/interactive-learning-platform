import { describe, it, expect } from "vitest";
import {
  getRedirectForStatus,
  getRouteForStep,
  ALLOWED_STEPS_BY_STATUS,
  REDIRECT_TARGET_BY_STATUS,
  type WizardStep,
  type MaterialStatus,
} from "../types";

describe("DocumentStatusGuard - types", () => {
  describe("ALLOWED_STEPS_BY_STATUS", () => {
    it("should define allowed steps for all material statuses", () => {
      const statusesWithSteps: MaterialStatus[] = [
        "uploaded",
        "parsing",
        "parsed",
        "generating",
        "done",
        "failed",
      ];

      for (const status of statusesWithSteps) {
        expect(ALLOWED_STEPS_BY_STATUS[status]).toBeDefined();
        expect(Array.isArray(ALLOWED_STEPS_BY_STATUS[status])).toBe(true);
        expect(ALLOWED_STEPS_BY_STATUS[status].length).toBeGreaterThan(0);
      }
    });

    it("uploaded should only allow upload", () => {
      expect(ALLOWED_STEPS_BY_STATUS.uploaded).toEqual(["upload"]);
    });

    it("parsing should only allow upload", () => {
      expect(ALLOWED_STEPS_BY_STATUS.parsing).toEqual(["upload"]);
    });

    it("parsed should allow topics and questions", () => {
      expect(ALLOWED_STEPS_BY_STATUS.parsed).toEqual(["topics", "questions"]);
    });

    it("generating should only allow progress", () => {
      expect(ALLOWED_STEPS_BY_STATUS.generating).toEqual(["progress"]);
    });

    it("done should only allow materials", () => {
      expect(ALLOWED_STEPS_BY_STATUS.done).toEqual(["materials"]);
    });

    it("failed should allow topics", () => {
      expect(ALLOWED_STEPS_BY_STATUS.failed).toEqual(["topics"]);
    });
  });

  describe("REDIRECT_TARGET_BY_STATUS", () => {
    it("should define redirect target for all material statuses", () => {
      const statuses: MaterialStatus[] = [
        "uploaded",
        "parsing",
        "parsed",
        "generating",
        "done",
        "failed",
      ];

      for (const status of statuses) {
        expect(REDIRECT_TARGET_BY_STATUS[status]).toBeDefined();
      }
    });

    it("uploaded should redirect to upload", () => {
      expect(REDIRECT_TARGET_BY_STATUS.uploaded).toBe("upload");
    });

    it("parsing should redirect to upload", () => {
      expect(REDIRECT_TARGET_BY_STATUS.parsing).toBe("upload");
    });

    it("parsed should redirect to topics", () => {
      expect(REDIRECT_TARGET_BY_STATUS.parsed).toBe("topics");
    });

    it("generating should redirect to progress", () => {
      expect(REDIRECT_TARGET_BY_STATUS.generating).toBe("progress");
    });

    it("done should redirect to materials", () => {
      expect(REDIRECT_TARGET_BY_STATUS.done).toBe("materials");
    });

    it("failed should redirect to topics", () => {
      expect(REDIRECT_TARGET_BY_STATUS.failed).toBe("topics");
    });
  });

  describe("getRedirectForStatus", () => {
    const testCases: Array<{
      status: MaterialStatus;
      currentStep: WizardStep;
      expectedRedirect: WizardStep | null;
    }> = [
      // uploaded status
      { status: "uploaded", currentStep: "upload", expectedRedirect: null },
      { status: "uploaded", currentStep: "topics", expectedRedirect: "upload" },
      {
        status: "uploaded",
        currentStep: "questions",
        expectedRedirect: "upload",
      },
      {
        status: "uploaded",
        currentStep: "progress",
        expectedRedirect: "upload",
      },
      {
        status: "uploaded",
        currentStep: "materials",
        expectedRedirect: "upload",
      },

      // parsing status
      { status: "parsing", currentStep: "upload", expectedRedirect: null },
      { status: "parsing", currentStep: "topics", expectedRedirect: "upload" },
      {
        status: "parsing",
        currentStep: "questions",
        expectedRedirect: "upload",
      },
      {
        status: "parsing",
        currentStep: "progress",
        expectedRedirect: "upload",
      },
      {
        status: "parsing",
        currentStep: "materials",
        expectedRedirect: "upload",
      },

      // parsed status - allows topics and questions
      { status: "parsed", currentStep: "upload", expectedRedirect: "topics" },
      { status: "parsed", currentStep: "topics", expectedRedirect: null },
      { status: "parsed", currentStep: "questions", expectedRedirect: null },
      { status: "parsed", currentStep: "progress", expectedRedirect: "topics" },
      {
        status: "parsed",
        currentStep: "materials",
        expectedRedirect: "topics",
      },

      // generating status
      {
        status: "generating",
        currentStep: "upload",
        expectedRedirect: "progress",
      },
      {
        status: "generating",
        currentStep: "topics",
        expectedRedirect: "progress",
      },
      {
        status: "generating",
        currentStep: "questions",
        expectedRedirect: "progress",
      },
      { status: "generating", currentStep: "progress", expectedRedirect: null },
      {
        status: "generating",
        currentStep: "materials",
        expectedRedirect: "progress",
      },

      // done status
      { status: "done", currentStep: "upload", expectedRedirect: "materials" },
      { status: "done", currentStep: "topics", expectedRedirect: "materials" },
      {
        status: "done",
        currentStep: "questions",
        expectedRedirect: "materials",
      },
      {
        status: "done",
        currentStep: "progress",
        expectedRedirect: "materials",
      },
      { status: "done", currentStep: "materials", expectedRedirect: null },

      // failed status - only topics allowed
      { status: "failed", currentStep: "upload", expectedRedirect: "topics" },
      { status: "failed", currentStep: "topics", expectedRedirect: null },
      {
        status: "failed",
        currentStep: "questions",
        expectedRedirect: "topics",
      },
      {
        status: "failed",
        currentStep: "progress",
        expectedRedirect: "topics",
      },
      {
        status: "failed",
        currentStep: "materials",
        expectedRedirect: "topics",
      },
    ];

    it.each(testCases)(
      "should return $expectedRedirect for status=$status, step=$currentStep",
      ({ status, currentStep, expectedRedirect }) => {
        const result = getRedirectForStatus(status, currentStep);
        expect(result).toBe(expectedRedirect);
      }
    );
  });

  describe("getRouteForStep", () => {
    const documentId = "doc-123";

    it("should return correct route for upload step", () => {
      expect(getRouteForStep("upload", documentId)).toBe(
        `/upload?document=${documentId}`
      );
    });

    it("should return correct route for topics step", () => {
      expect(getRouteForStep("topics", documentId)).toBe(
        `/documents/${documentId}/topics`
      );
    });

    it("should return correct route for questions step", () => {
      expect(getRouteForStep("questions", documentId)).toBe(
        `/documents/${documentId}/questions`
      );
    });

    it("should return correct route for progress step", () => {
      expect(getRouteForStep("progress", documentId)).toBe(
        `/documents/${documentId}/progress`
      );
    });

    it("should return correct route for materials step", () => {
      expect(getRouteForStep("materials", documentId)).toBe(`/materials`);
    });
  });
});
