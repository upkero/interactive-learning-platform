import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { z } from "zod";
import { designChecklist } from "../src/design/checklist.ts";
import { MVP_MODES, type AnyPrimitiveDefinition } from "../src/core/types.ts";
import { stableStringify } from "../src/core/serialization.ts";

const root = fileURLToPath(new URL("..", import.meta.url));
const output = process.argv[2] ? resolve(process.argv[2]) : resolve(root, "dist/catalog.json");
const css = readFileSync(resolve(root, "src/tokens/tokens.css"), "utf8");
const tokens = [...new Set([...css.matchAll(/(--g-[\w-]+)\s*:/g)].map(([, name]) => name))].sort();
// Vite resolves the actual runtime TSX exports and their CSS modules; types are erased.
const server = await createServer({ root, configFile: false, server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
try {
  const ui = await server.ssrLoadModule("/src/ui/index.ts");
  const { getPrimitives } = await server.ssrLoadModule("/src/registry.ts") as typeof import("../src/registry.ts");
  const primitives = getPrimitives().map((primitive: AnyPrimitiveDefinition) => {
    for (const example of primitive.examples) primitive.paramsSchema.parse(example.params);
    return {
      id: primitive.id, version: primitive.version, title: primitive.title,
      description: primitive.description,
      modes: primitive.modes.filter((mode) => MVP_MODES.includes(mode)),
      params_schema: z.toJSONSchema(primitive.paramsSchema, { io: "input", unrepresentable: "throw" }),
      label_keys: [...primitive.labelKeys],
      examples: primitive.examples.map(({ name, intent, mode, params }) => ({ name, intent, mode, params })),
    };
  });
  const catalog = { catalogVersion: 1, design: { checklist: designChecklist, tokens, ui_exports: Object.keys(ui).sort() }, primitives };
  mkdirSync(dirname(output), { recursive: true });
  writeFileSync(output, `${stableStringify(catalog)}\n`);
} finally { await server.close(); }
