import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

test('sandbox and production serve the same host page and CSP', () => {
  const page = readFileSync(new URL('../host.html', import.meta.url), 'utf8');
  const nginx = readFileSync(new URL('../nginx.conf', import.meta.url), 'utf8');
  const sandbox = readFileSync(new URL('../../sandbox/src/config.ts', import.meta.url), 'utf8');
  assert.match(page, /id="widget"/);
  assert.match(nginx, /connect-src 'none'/);
  assert.match(nginx, /script-src 'self' blob:/);
  const csp = sandbox.match(/export const HOST_CSP = "([^"]+)"/)?.[1];
  assert.ok(csp);
  assert.ok(nginx.includes(csp));
});
