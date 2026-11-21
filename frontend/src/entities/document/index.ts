export {
  MATERIALS_QUERY_KEY,
  type MaterialOut,
  useMaterials,
  useDeleteDocument,
  getMaterialRoute,
} from './model/useDocuments';

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
  useUploadDocument,
  useImportDocument,
  useGenerateDocument,
  usePlanDocument,
} from './model/useDocument';

export {
  type WizardStep,
  getRedirectForStatus,
  getRouteForStep,
  ALLOWED_STEPS_BY_STATUS,
  REDIRECT_TARGET_BY_STATUS,
} from './guard/types';

export {
  useDocumentStatusGuard,
  useDocumentErrorRedirect,
} from './guard/useDocumentStatusGuard';