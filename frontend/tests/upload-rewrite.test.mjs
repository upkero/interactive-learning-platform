import assert from "node:assert/strict";
import { Readable } from "node:stream";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { PHASE_PRODUCTION_SERVER } from "next/constants.js";
import bodyStreams from "next/dist/server/body-streams.js";
import nextConfig from "next/dist/server/config.js";

test("the Next rewrite can forward a maximum-size document and its multipart envelope", async () => {
  const frontend = fileURLToPath(new URL("..", import.meta.url));
  const config = await nextConfig.default(PHASE_PRODUCTION_SERVER, frontend);
  const head = Buffer.from(
    '--test\r\nContent-Disposition: form-data; name="file"; filename="sample.pdf"\r\n\r\n'
  );
  const tail = Buffer.from("\r\n--test--\r\n");
  const mebibyte = Buffer.alloc(1024 * 1024);
  const request = Readable.from([head, ...Array(50).fill(mebibyte), tail]);
  // External rewrites use this cloned body even when middleware excludes /api.
  const cloned = bodyStreams
    .getCloneableBody(request, config.experimental.middlewareClientMaxBodySize)
    .cloneBodyStream();

  let bytes = 0;
  for await (const chunk of cloned) {
    bytes += chunk.length;
  }
  assert.equal(bytes, head.length + 50 * mebibyte.length + tail.length);
});
