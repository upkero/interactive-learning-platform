import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
const root = resolve("storybook-static");
const types: Record<string, string> = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
};
createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(
      new URL(request.url ?? "/", "http://localhost").pathname
    );
    const file = resolve(
      root,
      `.${pathname === "/" ? "/index.html" : pathname}`
    );
    if (!file.startsWith(root + sep)) {
      response.writeHead(403).end();
      return;
    }
    response.setHeader(
      "Content-Type",
      types[extname(file)] ?? "application/octet-stream"
    );
    response.end(await readFile(file));
  } catch {
    response.writeHead(404).end();
  }
}).listen(6007, "127.0.0.1");
