import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { WidgetRunner } from './runner.js';
import { createServer } from './server.js';
import type { RunResponse } from './schema.js';

const payload = { source_tsx: 'export default () => null', param_sets: [{}], mode: 'watch', labels: {}, locale: 'en' };
const success: RunResponse = { ok: true, compiled_js: 'js', console_errors: [], screenshots: [], timings: {} };

test('health, schema, CSP, and compilation failure are handled without Chromium', async () => {
  const fake = { run: () => { throw new Error('should not run'); }, close: async () => undefined } as unknown as WidgetRunner;
  const app = createServer(fake);
  try {
    await app.ready();
    assert.equal((await app.inject('/health')).statusCode, 200);
    assert.equal((await app.inject('/host/host.html')).headers['content-security-policy'] !== undefined, true);
    assert.equal((await app.inject({ method: 'POST', url: '/run', payload: { ...payload, param_sets: [] } })).statusCode, 400);
    const syntax = await app.inject({ method: 'POST', url: '/run', payload: { ...payload, source_tsx: '<' } });
    assert.equal(syntax.statusCode, 200);
    assert.equal(syntax.json().ok, false);
    assert.equal(syntax.json().compiled_js, null);
  } finally {
    await app.close();
  }
});

test('at most two runs execute and eight wait, extra requests get 503', async () => {
  let running = 0;
  let maxRunning = 0;
  let started = 0;
  const gates: (() => void)[] = [];
  const fake = {
    run: async () => {
      started++;
      running++;
      maxRunning = Math.max(maxRunning, running);
      await new Promise<void>((resolve) => { gates.push(resolve); });
      running--;
      return success;
    },
    close: async () => undefined,
  } as unknown as WidgetRunner;
  const app = createServer(fake);
  try {
    await app.ready();
    const replies = Array.from({ length: 12 }, () => app.inject({ method: 'POST', url: '/run', payload }));
    // Wait until compilation and queue admission have completed, without a browser.
    while (gates.length < 2) await new Promise((resolve) => setTimeout(resolve, 10));
    assert.equal(maxRunning, 2);
    while (started < 10) {
      const release = gates.shift();
      release?.();
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    for (const release of gates) release();
    const results = await Promise.all(replies);
    assert.equal(results.filter((r) => r.statusCode === 503).length, 2);
    assert.equal(results.filter((r) => r.statusCode === 200).length, 10);
  } finally {
    for (const release of gates) release();
    await app.close();
  }
});
