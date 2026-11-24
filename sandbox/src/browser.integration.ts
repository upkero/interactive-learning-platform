import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createServer } from './server.js';

test('real Chromium: screenshots, runtime failures, denied network, and recovery after infinite loop',
  { timeout: 90_000 }, async () => {
    const app = createServer();
    await app.listen({ host: '127.0.0.1', port: 3001 });
    try {
      const send = async (source_tsx: string, param_sets = [{ value: 'one' }]) => {
        const response = await fetch('http://127.0.0.1:3001/run', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ source_tsx, param_sets, mode: 'watch', labels: {}, locale: 'en' }),
        });
        assert.equal(response.status, 200);
        return response.json() as Promise<{ ok: boolean; console_errors: string[];
          screenshots: string[]; timings: { total_ms: number } }>;
      };
      const valid = "export default function Widget({params}) { return <div>{params.value}</div>; }";
      const start = performance.now();
      const result = await send(valid, [{ value: 'one' }, { value: 'two' }, { value: 'three' }]);
      assert.equal(result.ok, true, JSON.stringify(result.console_errors));
      assert.deepEqual(result.console_errors, []);
      assert.equal(result.screenshots.length, 4);
      for (const shot of result.screenshots) {
        const png = Buffer.from(shot, 'base64');
        assert.equal(png.subarray(1, 4).toString('ascii'), 'PNG');
        assert.equal(png.readUInt32BE(16), 800);
        assert.equal(png.readUInt32BE(20), 500);
      }
      assert.ok(performance.now() - start < 10_000, 'render took longer than 10 seconds');

      const thrown = await send('export default function Widget() { throw new Error("boom"); }');
      assert.equal(thrown.ok, false);
      assert.match(thrown.console_errors.join(' '), /boom/);

      const blocked = await send('export default function Widget() { return <img src="https://example.com/x.png" />; }');
      assert.equal(blocked.ok, false);
      assert.match(blocked.console_errors.join(' '), /blocked request: https:\/\/example.com\/x.png/);

      const loop = await send('export default function Widget() { while (true) {} }');
      assert.equal(loop.ok, false);
      assert.ok(loop.timings.total_ms <= 30_500);
      assert.equal((await send(valid)).ok, true, 'browser must recover from stuck renderer');
    } finally {
      await app.close();
    }
  });
