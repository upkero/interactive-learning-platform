import { describe, expect, it } from "vitest";

import { getPrimitive, getPrimitives, primitiveRegistry } from "./registry";

describe("primitive registry", () => {
  it("exposes a stable, unique collection of primitives", () => {
    const ids = primitiveRegistry.map((primitive) => primitive.id);

    expect(new Set(ids).size).toBe(ids.length);
    expect(getPrimitives().map((primitive) => primitive.id)).toEqual([...ids].sort());
  });

  it("returns an undefined result for an unknown primitive id", () => {
    expect(getPrimitive("not-registered")).toBeUndefined();
  });
});
