import { z } from "zod";

import { MODES, MVP_MODES, type PrimitiveDefinition } from "./types";

const KEBAB_CASE = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;
const SEMVER = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

/** Throws when a schema contains behavior that cannot be represented in JSON Schema. */
export function assertCatalogSafeSchema(schema: z.ZodType): void {
  z.toJSONSchema(schema, { io: "input", unrepresentable: "throw" });

  const visited = new WeakSet<object>();
  const forbidden = new Set(["custom", "transform", "pipe"]);

  function visit(value: unknown): void {
    if (typeof value !== "object" || value === null || visited.has(value))
      return;
    visited.add(value);

    const definition = (
      value as { _zod?: { def?: { type?: string; check?: string } } }
    )._zod?.def;
    if (
      definition?.check === "custom" ||
      definition?.check === "overwrite" ||
      (definition?.type && forbidden.has(definition.type))
    ) {
      throw new Error(
        `Schema contains unsupported Zod ${definition.type ?? definition.check}; use a JSON Schema-compatible structure instead.`
      );
    }

    // superRefine checks live inside the non-enumerable _zod.def.
    if (definition) visit(definition);
    for (const child of Object.values(value)) visit(child);
  }

  visit(schema);
}

export function definePrimitive<Schema extends z.ZodType>(
  definition: PrimitiveDefinition<z.output<Schema>, z.input<Schema>> & {
    paramsSchema: Schema;
  }
): PrimitiveDefinition<z.output<Schema>, z.input<Schema>> & {
  paramsSchema: Schema;
} {
  if (!KEBAB_CASE.test(definition.id)) {
    throw new Error(`Primitive id must be kebab-case: ${definition.id}`);
  }
  if (!SEMVER.test(definition.version)) {
    throw new Error(`Primitive version must be semver: ${definition.version}`);
  }
  if (!definition.title.trim() || !definition.description.trim()) {
    throw new Error(
      "Primitive title and description must be non-empty English catalog text."
    );
  }
  if (
    definition.modes.length === 0 ||
    definition.modes.some((mode) => !MODES.includes(mode))
  ) {
    throw new Error("Primitive must declare one or more supported modes.");
  }
  if (definition.examples.length < 2 || definition.examples.length > 4) {
    throw new Error("Primitive must provide two to four resolver examples.");
  }
  if (!definition.modes.some((mode) => MVP_MODES.includes(mode))) {
    throw new Error("Primitive must support at least one MVP mode.");
  }
  if (new Set(definition.modes).size !== definition.modes.length) {
    throw new Error("Primitive modes must be unique.");
  }
  if (
    new Set(definition.examples.map((example) => example.name)).size !==
    definition.examples.length
  ) {
    throw new Error("Primitive example names must be unique.");
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
      throw new Error(
        `Example ${example.name} uses an unsupported mode: ${example.mode}`
      );
    }
    definition.paramsSchema.parse(example.params);
  }

  for (const mode of definition.modes.filter((item) =>
    MVP_MODES.includes(item)
  )) {
    if (!definition.examples.some((example) => example.mode === mode))
      throw new Error(`Primitive needs an example for mode: ${mode}`);
  }

  assertCatalogSafeSchema(definition.paramsSchema);
  return definition;
}
