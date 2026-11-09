import { z } from "zod";
import { MVP_MODES, type AnyPrimitiveDefinition } from "./types";

/** Convert definitions to the JSON-only contract consumed by the resolver. */
export function serializePrimitives(
  definitions: readonly AnyPrimitiveDefinition[]
) {
  return [...definitions]
    .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
    .map((primitive) => {
      for (const example of primitive.examples)
        primitive.paramsSchema.parse(example.params);
      return {
        id: primitive.id,
        version: primitive.version,
        title: primitive.title,
        description: primitive.description,
        modes: primitive.modes.filter((mode) => MVP_MODES.includes(mode)),
        paramsSchema: z.toJSONSchema(primitive.paramsSchema, {
          io: "input",
          unrepresentable: "throw",
        }),
        labelKeys: [...primitive.labelKeys],
        examples: primitive.examples.map(({ name, intent, mode, params }) => ({
          name,
          intent,
          mode,
          params,
        })),
      };
    });
}
