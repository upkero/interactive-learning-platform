import { build, type BuildFailure, type Plugin } from 'esbuild';
import * as React from 'react';
import * as jsxRuntime from 'react/jsx-runtime';
import * as d3 from 'd3';
import { ALLOWED_WIDGET_IMPORTS } from '@grasp/primitives/widget-protocol';

const allowed = new Set<string>(ALLOWED_WIDGET_IMPORTS);
const forbidden: ReadonlyArray<[RegExp, string]> = [
  [/\bfetch\s*\(/, 'fetch'], [/\bXMLHttpRequest\b/, 'XMLHttpRequest'],
  [/\bWebSocket\b/, 'WebSocket'], [/\bwindow\s*\.\s*parent\b/, 'window.parent'],
  [/\beval\s*\(/, 'eval'], [/\bnew\s+Function\b/, 'new Function'],
  [/\bimport\s*\(/, 'dynamic import'],
];

export type CompileResult = { ok: true; code: string } | { ok: false; errors: string[] };

// The virtual modules export references, not bundled copies: React must be the
// very same instance used by the host renderer (otherwise hooks break).
const exportNames: Record<string, string[]> = {
  react: Object.keys(React),
  'react/jsx-runtime': Object.keys(jsxRuntime),
  d3: Object.keys(d3),
  '@grasp/primitives/ui': ['Button', 'Slider', 'StepControls', 'Toggle'],
};
const globalsPlugin: Plugin = {
  name: 'grasp-globals',
  setup(plugin) {
    plugin.onResolve({ filter: /.*/ }, (args) => {
      if (args.kind === 'entry-point') return undefined;
      if (allowed.has(args.path)) return { path: args.path, namespace: 'grasp-global' };
      return { errors: [{ text: `Import "${args.path}" is not allowed` }] };
    });
    plugin.onLoad({ filter: /.*/, namespace: 'grasp-global' }, (args) => {
      const ref = `globalThis.__GRASP_DEPS__[${JSON.stringify(args.path)}]`;
      const names = exportNames[args.path] ?? [];
      return {
        contents: [
          ...names.filter((name) => /^[a-zA-Z_$][\w$]*$/.test(name) && name !== 'default')
            .map((name) => `export const ${name} = ${ref}[${JSON.stringify(name)}];`),
          `export default ${ref}.default ?? ${ref};`,
        ].join('\n'),
        loader: 'js',
      };
    });
  },
};

export async function compileWidget(sourceTsx: string): Promise<CompileResult> {
  const violations = forbidden.filter(([rule]) => rule.test(sourceTsx))
    .map(([, api]) => `Forbidden API: ${api}`);
  if (violations.length) return { ok: false, errors: violations };
  try {
    const result = await build({
      stdin: { contents: sourceTsx, loader: 'tsx', sourcefile: 'Widget.tsx', resolveDir: '/' },
      bundle: true, write: false, format: 'esm', jsx: 'automatic', target: 'es2022',
      logLevel: 'silent', plugins: [globalsPlugin],
    });
    const code = result.outputFiles[0]?.text;
    if (!code || !/export\s*\{[^}]*\bdefault\b|export\s+default\b/.test(code)) {
      return { ok: false, errors: ['compile: widget must have a default export'] };
    }
    return { ok: true, code };
  } catch (error) {
    const failure = error as BuildFailure;
    if (!Array.isArray(failure.errors)) throw error;
    return { ok: false, errors: failure.errors.map((item) =>
      `compile: ${item.text} (line ${item.location?.line ?? '?'})`) };
  }
}
