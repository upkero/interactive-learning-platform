import type { MaterialOut } from "../model/useDocuments";

/**
 * Wizard step identifiers corresponding to routes
 */
export type WizardStep =
  | "upload" // /upload?doc=[id]
  | "topics" // /documents/[id]/topics
  | "questions" // /documents/[id]/questions
  | "progress" // /documents/[id]/progress
  | "document"; // /documents/[id]

/**
 * Map of wizard step to its route pattern (without locale prefix)
 */
export const WIZARD_STEP_ROUTES: Record<
  WizardStep,
  (documentId: string) => string
> = {
  upload: (documentId) => `/upload?doc=${documentId}`,
  topics: (documentId) => `/documents/${documentId}/topics`,
  questions: (documentId) => `/documents/${documentId}/questions`,
  progress: (documentId) => `/documents/${documentId}/progress`,
  document: (documentId) => `/documents/${documentId}`,
};

/**
 * Material statuses from the new API:
 * uploaded, parsing, parsed, generating, done, failed
 */
export type MaterialStatus = MaterialOut["status"];

/**
 * Allowed steps for each material status.
 * Based on docs/ux/screens.md section 3 (adapted for new statuses):
 * - uploaded/parsing -> only upload allowed, others redirect to upload
 * - parsed -> topics allowed, questions/progress/document redirect to topics
 * - generating -> progress allowed, others redirect to progress
 * - done -> document allowed, others redirect to document
 * - failed -> none allowed, stay on materials (handled elsewhere)
 */
export const ALLOWED_STEPS_BY_STATUS: Record<MaterialStatus, WizardStep[]> = {
  uploaded: ["upload"],
  parsing: ["upload"],
  parsed: ["topics"],
  generating: ["progress"],
  done: ["document"],
  failed: [],
};

/**
 * For each status, the redirect target when accessing a disallowed step.
 */
export const REDIRECT_TARGET_BY_STATUS: Record<MaterialStatus, WizardStep> = {
  uploaded: "upload",
  parsing: "upload",
  parsed: "topics",
  generating: "progress",
  done: "document",
  failed: "document", // fallback, error handled elsewhere
};

/**
 * Check if a wizard step is allowed for a given material status.
 * Returns the redirect target step if not allowed, or null if allowed.
 */
export function getRedirectForStatus(
  materialStatus: MaterialStatus,
  currentStep: WizardStep
): WizardStep | null {
  const allowedSteps = ALLOWED_STEPS_BY_STATUS[materialStatus];

  if (allowedSteps.includes(currentStep)) {
    return null;
  }

  return REDIRECT_TARGET_BY_STATUS[materialStatus];
}

/**
 * Get the route string for a wizard step.
 */
export function getRouteForStep(step: WizardStep, documentId: string): string {
  return WIZARD_STEP_ROUTES[step](documentId);
}
