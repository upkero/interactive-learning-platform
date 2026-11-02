import { z } from "zod";

import { MODES, type PrimitiveDefinition } from "./types";

const KEBAB_CASE = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;
const SEMVER = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

/** Throws when a schema contains behavior that cannot be represented in JSON Schema. */
export function assertCatalogSafeSchema(schema: z.ZodType): void {
  z.toJSONSchema(schema, { io: "input", unrepresentable: "throw" });

  const visited = new WeakSet<object>();
  const forbidden = new Set(["custom", "transform", "pipe"]);

  function visit(value: unknown): void {
    if (typeof value !== "object" || value === null || visited.has(value)) return;
    visited.add(value);

    const definition = (value as { _zod?: { def?: { type?: string } } })._zod?.def;
    if (definition?.type && forbidden.has(definition.type)) {
      throw new Error(
        `Schema contains unsupported Zod ${definition.type}; use a JSON Schema-compatible structure instead.`,
      );
    }

    for (const child of Object.values(value)) visit(child);
  }

  visit(schema);
}

export function definePrimitive<Params>(
  definition: PrimitiveDefinition<Params>,
): PrimitiveDefinition<Params> {
  if (!KEBAB_CASE.test(definition.id)) {
    throw new Error(`Primitive id must be kebab-case: ${definition.id}`);
  }
  if (!SEMVER.test(definition.version)) {
    throw new Error(`Primitive version must be semver: ${definition.version}`);
  }
  if (!definition.title.trim() || !definition.description.trim()) {
    throw new Error("Primitive title and description must be non-empty English catalog text.");
  }
  if (definition.modes.length === 0 || definition.modes.some((mode) => !MODES.includes(mode))) {
    throw new Error("Primitive must declare one or more supported modes.");
  }
  if (definition.examples.length < 2 || definition.examples.length > 4) {
    throw new Error("Primitive must provide two to four resolver examples.");
  }
  if (new Set(definition.labelKeys).size !== definition.labelKeys.length) {
    throw new Error("Primitive labelKeys must not contain duplicates.");
  }

  for (const example of definition.examples) {
    if (!KEBAB_CASE.test(example.name)) {
      throw new Error(`Example name must be kebab-case: ${example.name}`);
    }
    if (!example.intent.trim()) {
      throw new Error(`Example intent must be non-empty: ${example.name}`);
    }
    if (!definition.modes.includes(example.mode)) {
      throw new Error(`Example ${example.name} uses an unsupported mode: ${example.mode}`);
    }
    definition.paramsSchema.parse(example.params);
  }

  assertCatalogSafeSchema(definition.paramsSchema);
  return definition;
}
