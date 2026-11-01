import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { designChecklist } from "../src/design/checklist.ts";

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

const catalog = {
  design: {
    checklist: designChecklist,
    tokens: collectTokens(readFileSync(tokensPath, "utf8")),
    uiExports: collectUiExports(readFileSync(uiIndexPath, "utf8")),
  },
};

mkdirSync(fileURLToPath(new URL("../dist", import.meta.url)), { recursive: true });
writeFileSync(catalogPath, `${JSON.stringify(catalog, null, 2)}\n`);
