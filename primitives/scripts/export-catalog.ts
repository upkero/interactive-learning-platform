import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { designChecklist } from "../src/design/checklist.ts";
import { stableStringify } from "../src/core/serialization.ts";

const root = fileURLToPath(new URL("..", import.meta.url));
const output = process.argv[2]
  ? resolve(process.argv[2])
  : resolve(root, "dist/catalog.json");
const css = readFileSync(resolve(root, "src/tokens/tokens.css"), "utf8");
const tokens = [
  ...new Set([...css.matchAll(/(--g-[\w-]+)\s*:/g)].map(([, name]) => name)),
].sort();
// Vite resolves the actual runtime TSX exports and their CSS modules; types are erased.
const server = await createServer({
  root,
  configFile: false,
  server: { middlewareMode: true, hmr: false, ws: false },
  appType: "custom",
});
try {
  const ui = await server.ssrLoadModule("/src/ui/index.ts");
  const { getPrimitives } = (await server.ssrLoadModule(
    "/src/registry.ts"
  )) as typeof import("../src/registry.ts");
  const { serializePrimitives } = (await server.ssrLoadModule(
    "/src/core/catalog.ts"
  )) as typeof import("../src/core/catalog.ts");
  const primitives = serializePrimitives(getPrimitives());
  const catalog = {
    catalog_version: 1,
    design: {
      checklist: designChecklist,
      tokens,
      uiExports: Object.keys(ui).sort(),
    },
    primitives,
  };
  mkdirSync(dirname(output), { recursive: true });
  writeFileSync(output, `${stableStringify(catalog)}\n`);
} finally {
  await server.close();
}
