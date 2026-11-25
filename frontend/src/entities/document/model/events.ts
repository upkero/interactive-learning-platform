import { z } from 'zod';

/**
 * SSE event types per contract 1.7:
 * stage, part_status, part_ready, document_done, error
 */
export const SseEventType = z.enum(['stage', 'part_status', 'part_ready', 'document_done', 'error']);

export const StageEventData = z.object({
  step: z.string(),
  progress: z.number().optional(),
});

export const PartStatusEventData = z.object({
  part_id: z.string().uuid(),
  status: z.enum(['queued', 'main_pass', 'resolving', 'assembling', 'published', 'failed']),
  title: z.string().optional(),
  index: z.number().optional(),
});

// PartContentOut is complex; we accept any object for content validation
export const PartReadyEventData = z.object({
  part_id: z.string().uuid(),
  content: z.record(z.unknown()),
});

export const DocumentDoneEventData = z.object({
  document_id: z.string().uuid(),
});

export const ErrorEventData = z.object({
  code: z.string(),
  detail: z.string().optional(),
});

export const SseEvent = z.object({
  id: z.string().optional(),
  event: SseEventType,
  data: z.union([
    StageEventData,
    PartStatusEventData,
    PartReadyEventData,
    DocumentDoneEventData,
    ErrorEventData,
    z.unknown(), // Unknown event types are safely ignored
  ]),
});

export type SseEventType = z.infer<typeof SseEventType>;
export type StageEventData = z.infer<typeof StageEventData>;
export type PartStatusEventData = z.infer<typeof PartStatusEventData>;
export type PartReadyEventData = z.infer<typeof PartReadyEventData>;
export type DocumentDoneEventData = z.infer<typeof DocumentDoneEventData>;
export type ErrorEventData = z.infer<typeof ErrorEventData>;
export type SseEvent = z.infer<typeof SseEvent>;

export function isFinalEvent(event: SseEvent): boolean {
  return event.event === 'document_done' || event.event === 'error';
}

export function parseSseEvent(raw: { event: string; data: string; id?: string }): SseEvent | null {
  try {
    const parsedData: unknown = JSON.parse(raw.data);
    return SseEvent.parse({
      id: raw.id,
      event: raw.event,
      data: parsedData,
    });
  } catch {
    // Unknown event type or invalid JSON - safely ignore
    return null;
  }
}