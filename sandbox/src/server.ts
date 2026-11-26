import Fastify from 'fastify';
import fastifyStatic from '@fastify/static';
import pLimit from 'p-limit';
import { compileWidget } from './compile.js';
import { WidgetRunner } from './runner.js';
import { runRequestSchema, type RunRequest, type RunResponse } from './schema.js';
import { config, HOST_CSP } from './config.js';

export function createServer(runner = new WidgetRunner(config.origin)) {
  const app = Fastify({ logger: true, bodyLimit: 512 * 1024 });
  app.addHook('onClose', () => runner.close());
  const limit = pLimit(config.concurrency);
  void app.register(fastifyStatic, {
    root: config.publicDir, prefix: '/host/',
    setHeaders: (res) => { res.setHeader('Content-Security-Policy', HOST_CSP); },
  });
  app.get('/health', async () => ({ status: 'ok' }));
  app.post<{ Body: RunRequest }>('/run', { schema: { body: runRequestSchema } }, async (request, reply) => {
    if (limit.pendingCount >= config.maxQueue) return reply.code(503).send({ error: 'busy' });
    const started = performance.now();
    const signal = AbortSignal.timeout(config.totalTimeoutMs);
    return limit(async (): Promise<RunResponse> => {
      try {
        if (signal.aborted) throw signal.reason;
        const compiled = await Promise.race([
          compileWidget(request.body.source_tsx),
          new Promise<never>((_, reject) => signal.addEventListener('abort', () => reject(signal.reason), { once: true })),
        ]);
        if (!compiled.ok) return { ok: false, compiled_js: null, console_errors: compiled.errors,
          screenshots: [], timings: { total_ms: Math.round(performance.now() - started) } };
        const result = await runner.run({ ...request.body, viewport: request.body.viewport ?? { w: 800, h: 500 } },
          compiled.code, signal);
        return { ...result, timings: { ...result.timings, total_ms: Math.round(performance.now() - started) } };
      } catch (error) {
        if (!signal.aborted) throw error;
        return { ok: false, compiled_js: null, console_errors: ['timeout: sandbox run exceeded 30 s'],
          screenshots: [], timings: { total_ms: Math.round(performance.now() - started) } };
      }
    });
  });
  return app;
}
