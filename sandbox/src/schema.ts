export type RunRequest = {
  source_tsx: string;
  param_sets: Record<string, unknown>[];
  mode: 'watch' | 'steps' | 'predict';
  labels: Record<string, string>;
  locale: string;
  viewport: { w: number; h: number };
};

export type RunResponse = {
  ok: boolean;
  compiled_js: string | null;
  console_errors: string[];
  screenshots: string[];
  timings: { render_ms?: number[]; total_ms?: number };
};

export const runRequestSchema = {
  type: 'object',
  required: ['source_tsx', 'param_sets', 'mode', 'labels', 'locale'],
  additionalProperties: false,
  properties: {
    source_tsx: { type: 'string', minLength: 1, maxLength: 500_000 },
    param_sets: {
      type: 'array', minItems: 1, maxItems: 3,
      items: { type: 'object', additionalProperties: true },
    },
    mode: { type: 'string', enum: ['watch', 'steps', 'predict'] },
    labels: { type: 'object', additionalProperties: { type: 'string' } },
    locale: { type: 'string', minLength: 2, maxLength: 35 },
    viewport: {
      type: 'object', required: ['w', 'h'], additionalProperties: false,
      properties: {
        w: { type: 'integer', minimum: 1, maximum: 1920 },
        h: { type: 'integer', minimum: 1, maximum: 1080 },
      },
      default: { w: 800, h: 500 },
    },
  },
} as const;
