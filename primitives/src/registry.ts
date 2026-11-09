import type { AnyPrimitiveDefinition } from "./core/types";

/**
 * Single source of truth for primitives bundled in this package.
 *
 * Concrete primitive modules are appended here as they are implemented in
 * section 3.4. Keeping the list here makes the browser registry and the
 * published catalog describe exactly the same set.
 */
export const primitiveRegistry: readonly AnyPrimitiveDefinition[] = [];

const primitivesById = new Map(
  primitiveRegistry.map((primitive) => [primitive.id, primitive])
);
if (primitivesById.size !== primitiveRegistry.length)
  throw new Error("Duplicate primitive id.");

/** Return a bundled primitive by its stable catalog id, if it is available. */
export function getPrimitive(id: string): AnyPrimitiveDefinition | undefined {
  return primitivesById.get(id);
}

/** Return the registry in stable id order for catalog generation. */
export function getPrimitives(): readonly AnyPrimitiveDefinition[] {
  return [...primitiveRegistry].sort((left, right) =>
    left.id < right.id ? -1 : left.id > right.id ? 1 : 0
  );
}
