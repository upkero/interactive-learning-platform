export {
  MATERIALS_QUERY_KEY,
  type MaterialOut,
  useMaterials,
  getMaterialRoute,
} from "./model/useDocuments";

export {
  DOCUMENT_QUERY_KEY,
  type DocumentOut,
  type PartSummaryOut,
  type PartOut,
  type TopicNodeOut,
  type TopicTreeOut,
  type GenerateRequest,
  type GenerateResponse,
  type PlanRequest,
  type PlanResponse,
  type DocumentPart,
  useDocument,
  useDocumentTopics,
  useDocumentParts,
  usePart,
  useGenerateDocument,
} from "./model/useDocument";

export {
  type WizardStep,
  getRedirectForStatus,
  getRouteForStep,
  ALLOWED_STEPS_BY_STATUS,
  REDIRECT_TARGET_BY_STATUS,
} from "./guard/types";

export {
  useDocumentStatusGuard,
  useDocumentErrorRedirect,
} from "./guard/useDocumentStatusGuard";

export {
  SseEventType,
  type StageEventData,
  type PartStatusEventData,
  type PartReadyEventData,
  type DocumentDoneEventData,
  type ErrorEventData,
  type SseEvent,
  isFinalEvent,
  parseSseEvent,
} from "./model/events";
