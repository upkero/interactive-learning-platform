import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

export const config = {
  port: 3001,
  origin: process.env.SANDBOX_ORIGIN ?? 'http://127.0.0.1:3001',
  publicDir: resolve(process.env.SANDBOX_PUBLIC_DIR ?? resolve(dirname(fileURLToPath(import.meta.url)),
    '../../widget-host/dist')),
  concurrency: 2,
  maxQueue: 8,
  totalTimeoutMs: 30_000,
};

// CSP shared with the production host (widget-host/nginx.conf).
export const HOST_CSP = "default-src 'none'; script-src 'self' blob:; style-src 'self' 'unsafe-inline'; img-src * data: blob:; font-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors *";
