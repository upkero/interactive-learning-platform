import * as React from 'react';
import * as JSX from 'react/jsx-runtime';
import * as d3 from 'd3';
import { createRoot } from 'react-dom/client';
import * as ui from '@grasp/primitives/ui';
import '@grasp/primitives/tokens.css';
import type { InitMessage, WidgetToHost } from '@grasp/primitives/widget-protocol';

declare global {
  interface Window {
    __GRASP_DEPS__: Record<string, unknown>;
    __graspHarness: { init(message: InitMessage): Promise<void>; outbox: WidgetToHost[] };
  }
}

window.__GRASP_DEPS__ = {
  react: React,
  'react/jsx-runtime': JSX,
  d3,
  '@grasp/primitives/ui': ui,
};

const outbox: WidgetToHost[] = [];
let generation = 0;
let parentOrigin: string | null = null;
function send(message: WidgetToHost): void {
  outbox.push(message);
  if (parentOrigin) window.parent.postMessage(message, parentOrigin);
}

const container = document.getElementById('widget');
if (!container) throw new Error('widget root missing');
const root = createRoot(container, { onUncaughtError: (error) => {
  send({ type: 'grasp:error', message: String(error) });
} });

function Ready({ run }: { run: number }): React.ReactElement {
  React.useEffect(() => {
    requestAnimationFrame(() => {
      if (run === generation) {
        send({ type: 'grasp:ready' });
        send({ type: 'grasp:resize', height: document.documentElement.scrollHeight });
      }
    });
  }, [run]);
  return <></>;
}

async function init(message: InitMessage): Promise<void> {
  const run = ++generation;
  document.documentElement.dataset.theme = message.theme;
  document.documentElement.lang = message.locale;
  const blob = URL.createObjectURL(new Blob([message.code], { type: 'text/javascript' }));
  try {
    const module = await import(/* @vite-ignore */ blob) as { default?: React.ComponentType<Record<string, unknown>> };
    if (run !== generation) return;
    if (typeof module.default !== 'function') throw new Error('Widget must export a component as default');
    const Widget = module.default;
    root.render(<><Widget params={message.params} mode={message.mode} labels={message.labels} /><Ready run={run} /></>);
  } catch (error) {
    send({ type: 'grasp:error', message: String(error) });
  } finally {
    URL.revokeObjectURL(blob);
  }
}

window.__graspHarness = { outbox, init };
// In a sandboxed iframe, only its parent may initialize it. The parent must
// use an iframe without allow-same-origin; no trusted origin is inferred from
// the URL supplied by an untrusted embedder.
window.addEventListener('message', (event: MessageEvent<InitMessage>) => {
  if (window.parent === window || event.source !== window.parent || event.data?.type !== 'grasp:init') return;
  parentOrigin = event.origin;
  void init(event.data);
});
