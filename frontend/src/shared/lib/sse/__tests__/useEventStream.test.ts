import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useEventStream } from '../useEventStream';

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  listeners: Partial<Record<string, ((e: MessageEvent) => void)[]>> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, cb: (e: MessageEvent) => void) {
    (this.listeners[type] ??= []).push(cb);
  }

  emit(type: string, data: unknown, lastEventId = '') {
    const event = { data: JSON.stringify(data), lastEventId } as MessageEvent;
    if (type === 'message' && this.onmessage) this.onmessage(event);
    for (const cb of this.listeners[type] ?? []) {
      cb(event);
    }
  }

  close() {
    this.closed = true;
  }
}

describe('useEventStream', () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.useFakeTimers();
    vi.stubGlobal('EventSource', MockEventSource);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('connects, tracks last_event_id and reconnects with exponential backoff', () => {
    const events: unknown[] = [];
    const { result } = renderHook(() =>
      useEventStream({
        url: 'http://localhost:8000/api/v1/documents/1/events',
        onEvent: (e) => events.push(e),
      })
    );

    expect(result.current.status).toBe('connecting');
    const es1 = MockEventSource.instances[0];

    act(() => {
      es1.onopen?.();
    });
    expect(result.current.status).toBe('open');

    act(() => {
      es1.emit('stage', { step: 'parsing' }, 'evt-42');
    });
    expect(result.current.lastEventId).toBe('evt-42');

    act(() => {
      es1.onerror?.();
    });
    expect(result.current.status).toBe('reconnecting');

    act(() => {
      vi.advanceTimersByTime(2000); // Enough to cover initial backoff + jitter
    });

    const es2 = MockEventSource.instances[1];
    expect(es2).toBeDefined();
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion, @typescript-eslint/no-non-null-assertion
    expect(es2!.url).toContain('last_event_id=evt-42');
  });

  it('closes on terminal event (document_done) without reconnecting', () => {
    const { result } = renderHook(() =>
      useEventStream({
        url: 'http://localhost:8000/api/v1/documents/1/events',
      })
    );

    const es1 = MockEventSource.instances[0];

    act(() => {
      es1.onopen?.();
    });
    expect(result.current.status).toBe('open');

    act(() => {
      es1.emit('document_done', { document_id: 'doc-1' });
    });

    expect(result.current.status).toBe('closed');
    expect(MockEventSource.instances.length).toBe(1); // No reconnection
  });

  it('closes on error event without reconnecting', () => {
    const { result } = renderHook(() =>
      useEventStream({
        url: 'http://localhost:8000/api/v1/documents/1/events',
      })
    );

    const es1 = MockEventSource.instances[0];

    act(() => {
      es1.onopen?.();
    });
    expect(result.current.status).toBe('open');

    act(() => {
      es1.emit('error', { code: 'generation_failed', detail: 'Something went wrong' });
    });

    expect(result.current.status).toBe('closed');
    expect(MockEventSource.instances.length).toBe(1);
  });

  it('uses relative URL without withCredentials', () => {
    renderHook(() =>
      useEventStream({
        url: '/api/v1/documents/1/events',
      })
    );

    const es1 = MockEventSource.instances[0];
    expect(es1.url).toContain('/api/v1/documents/1/events');
    // EventSource by default doesn't send credentials for same-origin relative URLs
  });

  it('respects custom eventTypes from caller', () => {
    const events: string[] = [];
    renderHook(() =>
      useEventStream({
        url: 'http://localhost:8000/api/v1/documents/1/events',
        eventTypes: ['custom_event'],
        onEvent: (e) => events.push(e.event),
      })
    );

    const es1 = MockEventSource.instances[0];

    act(() => {
      es1.onopen?.();
    });

    act(() => {
      es1.emit('custom_event', { foo: 'bar' });
    });

    expect(events).toContain('custom_event');
  });

  it('backoff grows with jitter and caps at maxBackoffMs', () => {
    const { result } = renderHook(() =>
      useEventStream({
        url: 'http://localhost:8000/api/v1/documents/1/events',
        initialBackoffMs: 1000,
        maxBackoffMs: 5000,
      })
    );

    const es1 = MockEventSource.instances[0];

    act(() => {
      es1.onopen?.();
    });

    // First error -> retry after ~1000ms (±20%)
    act(() => {
      es1.onerror?.();
    });
    expect(result.current.status).toBe('reconnecting');

    act(() => {
      vi.advanceTimersByTime(1200); // Past first backoff
    });

    const es2 = MockEventSource.instances[1];
    expect(es2).toBeDefined();

    // Second error -> retry after ~2000ms (±20%)
    act(() => {
      es2.onerror?.();
    });

    act(() => {
      vi.advanceTimersByTime(2400);
    });

    const es3 = MockEventSource.instances[2];
    expect(es3).toBeDefined();

    // Third error -> retry after ~4000ms (±20%)
    act(() => {
      es3.onerror?.();
    });

    act(() => {
      vi.advanceTimersByTime(4800);
    });

    const es4 = MockEventSource.instances[3];
    expect(es4).toBeDefined();

    // Fourth error -> capped at 5000ms (±20%)
    act(() => {
      es4.onerror?.();
    });

    act(() => {
      vi.advanceTimersByTime(6000);
    });

    const es5 = MockEventSource.instances[4];
    expect(es5).toBeDefined();
  });

  it('resets backoff on successful reconnect (onopen)', () => {
    renderHook(() =>
      useEventStream({
        url: 'http://localhost:8000/api/v1/documents/1/events',
        initialBackoffMs: 1000,
        maxBackoffMs: 30000,
      })
    );

    const es1 = MockEventSource.instances[0];

    act(() => {
      es1.onopen?.();
    });

    act(() => {
      es1.onerror?.();
    });

    act(() => {
      vi.advanceTimersByTime(1200);
    });

    const es2 = MockEventSource.instances[1];

    act(() => {
      es2.onopen?.();
    });

    // Backoff should reset to initial
    act(() => {
      es2.onerror?.();
    });

    act(() => {
      vi.advanceTimersByTime(1200);
    });

    const es3 = MockEventSource.instances[2];
    expect(es3).toBeDefined();
  });
});