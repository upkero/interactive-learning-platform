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
  terminalEvents?: string[];
  onEvent?: (message: SseEventMessage<T>) => void;
  maxBackoffMs?: number;
  initialBackoffMs?: number;
}

const DEFAULT_TERMINAL_EVENTS: string[] = ['document_done', 'parsing_done', 'fatal_error'];

export function useEventStream<T = unknown>({
  url,
  enabled = true,
  terminalEvents = DEFAULT_TERMINAL_EVENTS,
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

  useEffect(() => {
    if (!url || !enabled) {
      cleanup();
      setStatus('idle');
      return;
    }

    isTerminalRef.current = false;

    const connect = () => {
      cleanup();
      setStatus(retryAttemptRef.current === 0 ? 'connecting' : 'reconnecting');

      const targetUrl = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
      if (lastEventIdRef.current) {
        targetUrl.searchParams.set('last_event_id', lastEventIdRef.current);
      }

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

        if (terminalEvents.includes(eventType)) {
          isTerminalRef.current = true;
          cleanup();
          setStatus('closed');
        }
      };

      es.onmessage = (e) => {
        handleRawEvent('message', e);
      };

      for (const evtName of ['stage', 'part_status', 'key_term', ...terminalEvents]) {
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
        const delay = Math.min(maxBackoffMs, initialBackoffMs * 2 ** retryAttemptRef.current);
        retryAttemptRef.current += 1;

        timerRef.current = setTimeout(() => {
          connect();
        }, delay);
      };
    };

    connect();

    return () => {
      cleanup();
    };
  }, [url, enabled, cleanup, initialBackoffMs, maxBackoffMs, terminalEvents]);

  return { status, lastEventId, close: cleanup };
}
