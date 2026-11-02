import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { z } from "zod";

import { designChecklist } from "../src/design/checklist.ts";
import type { PrimitiveDefinition } from "../src/core/types.ts";
import { getPrimitives } from "../src/registry.ts";

const root = fileURLToPath(new URL("..", import.meta.url));
const tokensPath = `${root}/src/tokens/tokens.css`;
const uiIndexPath = `${root}/src/ui/index.ts`;
const catalogPath = `${root}/dist/catalog.json`;

function sortedUnique(values: Iterable<string>) {
  return [...new Set(values)].sort((left, right) => left.localeCompare(right));
}

function collectTokens(css: string) {
  return sortedUnique([...css.matchAll(/(--g-[\w-]+)\s*:/g)].map(([, name]) => name));
}

function collectUiExports(index: string) {
  return sortedUnique(
    [...index.matchAll(/export\s*{\s*([A-Za-z][\w]*)/g)].map(([, name]) => name),
  );
}

function exportPrimitive(primitive: PrimitiveDefinition<unknown>) {
  return {
    id: primitive.id,
    version: primitive.version,
    title: primitive.title,
    description: primitive.description,
    modes: [...primitive.modes],
    params_schema: z.toJSONSchema(primitive.paramsSchema, {
      io: "input",
      unrepresentable: "throw",
    }),
    label_keys: [...primitive.labelKeys],
    examples: primitive.examples.map((example) => ({
      name: example.name,
      intent: example.intent,
      mode: example.mode,
      params: example.params,
    })),
  };
}

const catalog = {
  catalogVersion: 1,
  design: {
    checklist: designChecklist,
    tokens: collectTokens(readFileSync(tokensPath, "utf8")),
    uiExports: collectUiExports(readFileSync(uiIndexPath, "utf8")),
  },
  primitives: getPrimitives().map(exportPrimitive),
};

mkdirSync(fileURLToPath(new URL("../dist", import.meta.url)), { recursive: true });
writeFileSync(catalogPath, `${JSON.stringify(catalog, null, 2)}\n`);
