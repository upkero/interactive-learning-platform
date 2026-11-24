import { chromium, type Browser, type BrowserContext } from 'playwright';
import type { InitMessage, WidgetToHost } from '@grasp/primitives/widget-protocol';
import type { RunRequest, RunResponse } from './schema.js';

declare global {
  interface Window {
    __graspHarness: {
      outbox: WidgetToHost[];
      init(message: InitMessage): Promise<void>;
    };
  }
}

export class WidgetRunner {
  private browser: Browser | null = null;
  private runs = 0;
  private active = 0;
  private launching: Promise<Browser> | null = null;

  constructor(private readonly origin: string, private readonly renderTimeoutMs = 5_000) {}

  async run(req: RunRequest, compiledJs: string, signal: AbortSignal): Promise<RunResponse> {
    const browser = await this.ensureBrowser();
    this.active += 1;
    let context: BrowserContext;
    try {
      context = await browser.newContext({
      viewport: { width: req.viewport.w, height: req.viewport.h }, serviceWorkers: 'block',
      });
    } catch (error) {
      this.active -= 1;
      throw error;
    }
    const errors: string[] = [];
    const screenshots: string[] = [];
    const renderMs: number[] = [];
    const abort = () => { void context.close().catch(() => undefined); };
    signal.addEventListener('abort', abort, { once: true });
    try {
      await context.route('**/*', (route) => {
        const url = route.request().url();
        // Parse the origin, never use startsWith: sandbox.example.attacker is not local.
        if (new URL(url).origin === this.origin) return route.continue();
        errors.push(`blocked request: ${url}`);
        return route.abort('blockedbyclient');
      });
      const page = await context.newPage();
      page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()); });
      page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
      await page.goto(`${this.origin}/host/host.html`, { waitUntil: 'load', timeout: this.renderTimeoutMs });
      const renders: { params: Record<string, unknown>; theme: 'light' | 'dark' }[] = [
        ...req.param_sets.map((params) => ({ params, theme: 'light' as const })),
        { params: req.param_sets[0], theme: 'dark' },
      ];
      let ready = true;
      for (const { params, theme } of renders) {
        const started = performance.now();
        const renderSignal = AbortSignal.any([signal, AbortSignal.timeout(this.renderTimeoutMs)]);
        const init: InitMessage = { type: 'grasp:init', code: compiledJs, params, mode: req.mode,
          labels: req.labels, theme, locale: req.locale };
        try {
          const from = await this.withDeadline(page.evaluate((message) => {
            const harness = window.__graspHarness;
            const index = harness.outbox.length;
            void harness.init(message);
            return index;
          }, init), renderSignal);
          const outcome = await this.withDeadline(page.waitForFunction(
            (start) => window.__graspHarness.outbox.slice(start)
              .find((message) => message.type === 'grasp:ready' || message.type === 'grasp:error') ?? null,
            from, { timeout: this.renderTimeoutMs },
          ).then((handle) => handle.jsonValue() as Promise<WidgetToHost>), renderSignal);
          if (outcome.type !== 'grasp:ready') {
            ready = false;
            errors.push(`grasp:error: ${outcome.type === 'grasp:error' ? outcome.message : 'not ready'}`);
            break;
          }
          const image = await this.withDeadline(page.screenshot({ type: 'png', timeout: this.renderTimeoutMs }), renderSignal);
          screenshots.push(image.toString('base64'));
        } catch (error) {
          ready = false;
          errors.push(signal.aborted ? 'timeout: sandbox run exceeded 30 s' :
            renderSignal.aborted ? 'timeout: no grasp:ready' :
              `render failed: ${error instanceof Error ? error.message : String(error)}`);
          break;
        } finally {
          renderMs.push(Math.round(performance.now() - started));
        }
      }
      return { ok: ready && errors.length === 0, compiled_js: compiledJs,
        console_errors: errors, screenshots, timings: { render_ms: renderMs } };
    } finally {
      signal.removeEventListener('abort', abort);
      await context.close().catch(() => undefined);
      this.runs += 1;
      this.active -= 1;
    }
  }

  private async withDeadline<T>(operation: Promise<T>, signal: AbortSignal): Promise<T> {
    if (signal.aborted) throw signal.reason;
    let onAbort: (() => void) | undefined;
    try {
      return await Promise.race([
        operation,
        new Promise<T>((_, reject) => {
          onAbort = () => reject(signal.reason);
          signal.addEventListener('abort', onAbort, { once: true });
          if (signal.aborted) onAbort();
        }),
      ]);
    } finally {
      if (onAbort) signal.removeEventListener('abort', onAbort);
    }
  }

  private async ensureBrowser(): Promise<Browser> {
    if (this.browser?.isConnected() && (this.runs < 200 || this.active > 0)) return this.browser;
    if (this.launching) return this.launching;
    this.launching = (async () => {
      await this.browser?.close().catch(() => undefined);
      this.browser = await chromium.launch({ chromiumSandbox: true });
      const launched = this.browser;
      launched.on('disconnected', () => { if (this.browser === launched) this.browser = null; });
      this.runs = 0;
      return this.browser;
    })();
    try { return await this.launching; } finally { this.launching = null; }
  }

  async close(): Promise<void> {
    await this.browser?.close();
    this.browser = null;
  }
}
