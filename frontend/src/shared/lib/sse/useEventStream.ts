'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type StreamConnectionStatus = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed';

export interface SseEventMessage<T = unknown> {
  id?: string;
  event: string;
  data: T;
}

export interface UseEventStreamOptions<T = unknown> {
  url: string | null;
  enabled?: boolean;
  eventTypes?: string[];
  onEvent?: (message: SseEventMessage<T>) => void;
  maxBackoffMs?: number;
  initialBackoffMs?: number;
}

/**
 * Contract 1.7 event types:
 * stage, part_status, part_ready, document_done, error
 */
const CONTRACT_EVENT_TYPES = ['stage', 'part_status', 'part_ready', 'document_done', 'error'] as const;
const TERMINAL_EVENTS = ['document_done', 'error'] as const;

export function useEventStream<T = unknown>({
  url,
  enabled = true,
  eventTypes = [...CONTRACT_EVENT_TYPES],
  onEvent,
  maxBackoffMs = 30_000,
  initialBackoffMs = 1_000,
}: UseEventStreamOptions<T>) {
  const [status, setStatus] = useState<StreamConnectionStatus>('idle');
  const [lastEventId, setLastEventId] = useState<string | null>(null);

  const lastEventIdRef = useRef<string | null>(null);
  const retryAttemptRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const isTerminalRef = useRef(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;
  const eventTypesRef = useRef(eventTypes);
  eventTypesRef.current = eventTypes;

  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!url || !enabled) return;

    cleanup();
    isTerminalRef.current = false;
    setStatus(retryAttemptRef.current === 0 ? 'connecting' : 'reconnecting');

    const targetUrl = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
    if (lastEventIdRef.current) {
      targetUrl.searchParams.set('last_event_id', lastEventIdRef.current);
    }

    // Contract 1.7: no withCredentials (relative URL, same-origin)
    const es = new EventSource(targetUrl.toString());
    esRef.current = es;

    es.onopen = () => {
      retryAttemptRef.current = 0;
      setStatus('open');
    };

    const handleRawEvent = (eventType: string, rawEvent: MessageEvent<unknown>) => {
      if (rawEvent.lastEventId) {
        lastEventIdRef.current = rawEvent.lastEventId;
        setLastEventId(rawEvent.lastEventId);
      }

      let parsedData: T;
      try {
        parsedData = JSON.parse(String(rawEvent.data)) as T;
      } catch {
        parsedData = rawEvent.data as T;
      }

      onEventRef.current?.({
        id: rawEvent.lastEventId || undefined,
        event: eventType,
        data: parsedData,
      });

      if (TERMINAL_EVENTS.includes(eventType as typeof TERMINAL_EVENTS[number])) {
        isTerminalRef.current = true;
        cleanup();
        setStatus('closed');
      }
    };

    // Listen for message event (no event type)
    es.onmessage = (e) => {
      handleRawEvent('message', e);
    };

    // Listen for specific event types
    for (const evtName of eventTypesRef.current) {
      es.addEventListener(evtName, (e) => {
        handleRawEvent(evtName, e);
      });
    }

    es.onerror = () => {
      es.close();
      esRef.current = null;

      if (isTerminalRef.current) {
        setStatus('closed');
        return;
      }

      setStatus('reconnecting');
      // Exponential backoff with ±20% jitter
      const baseDelay = Math.min(maxBackoffMs, initialBackoffMs * 2 ** retryAttemptRef.current);
      const jitter = baseDelay * 0.2 * (Math.random() * 2 - 1); // ±20%
      const delay = Math.min(maxBackoffMs, Math.max(0, baseDelay + jitter));
      retryAttemptRef.current += 1;

      timerRef.current = setTimeout(() => {
        connect();
      }, delay);
    };
  }, [url, enabled, cleanup, initialBackoffMs, maxBackoffMs]);

  useEffect(() => {
    if (!url || !enabled) {
      cleanup();
      setStatus('idle');
      return;
    }

    connect();

    return () => {
      cleanup();
    };
  }, [url, enabled, connect, cleanup]);

  return { status, lastEventId, close: cleanup };
}