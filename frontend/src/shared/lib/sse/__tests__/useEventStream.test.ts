import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useEventStream } from '../useEventStream';

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, cb: (e: MessageEvent) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(cb);
  }

  emit(type: string, data: unknown, lastEventId = '') {
    const event = { data: JSON.stringify(data), lastEventId } as MessageEvent;
    if (type === 'message' && this.onmessage) this.onmessage(event);
    for (const cb of this.listeners[type] || []) {
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
      vi.advanceTimersByTime(1000);
    });

    const es2 = MockEventSource.instances[1];
    expect(es2.url).toContain('last_event_id=evt-42');
  });
});
