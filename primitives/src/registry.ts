import type { PrimitiveDefinition } from "./core/types";

/**
 * Single source of truth for primitives bundled in this package.
 *
 * Concrete primitive modules are appended here as they are implemented in
 * section 3.4. Keeping the list here makes the browser registry and the
 * published catalog describe exactly the same set.
 */
export const primitiveRegistry: readonly PrimitiveDefinition<unknown>[] = [];

const primitivesById = new Map(primitiveRegistry.map((primitive) => [primitive.id, primitive]));

/** Return a bundled primitive by its stable catalog id, if it is available. */
export function getPrimitive(id: string): PrimitiveDefinition<unknown> | undefined {
  return primitivesById.get(id);
}

/** Return the registry in stable id order for catalog generation. */
export function getPrimitives(): readonly PrimitiveDefinition<unknown>[] {
  return [...primitiveRegistry].sort((left, right) => left.id.localeCompare(right.id));
}
