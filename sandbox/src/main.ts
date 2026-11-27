import { config } from './config.js';
import { createServer } from './server.js';

await createServer().listen({ host: '0.0.0.0', port: config.port });
