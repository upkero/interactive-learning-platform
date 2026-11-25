// Base query keys
export const qk = {
  me: ['me'] as const,
  quota: ['me', 'quota'] as const,
  materials: (filter: 'mine' | 'shared' = 'mine') => ['materials', filter] as const,
  document: (documentId: string) => ['document', documentId] as const,
  documentTopics: (documentId: string) => ['document', documentId, 'topics'] as const,
  documentParts: (documentId: string) => ['document', documentId, 'parts'] as const,
  part: (partId: string) => ['part', partId] as const,
} as const;

// Type helpers for query key inference
export type MeQueryKey = typeof qk.me;
export type QuotaQueryKey = typeof qk.quota;
export type MaterialsQueryKey = ReturnType<typeof qk.materials>;
export type DocumentQueryKey = ReturnType<typeof qk.document>;
export type DocumentTopicsQueryKey = ReturnType<typeof qk.documentTopics>;
export type DocumentPartsQueryKey = ReturnType<typeof qk.documentParts>;
export type PartQueryKey = ReturnType<typeof qk.part>;