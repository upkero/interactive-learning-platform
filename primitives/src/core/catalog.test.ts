import { readFileSync } from "node:fs";
import Ajv2020 from "ajv/dist/2020";
import { describe, expect, it } from "vitest";
import { getPrimitives } from "../registry";
import { stableStringify } from "./serialization";

describe("published resolver catalog", () => {
  const contents = readFileSync("dist/catalog.json", "utf8");
  const catalog = JSON.parse(contents);
  it("is canonical, synchronized and includes all registered examples", () => {
    expect(contents).toBe(stableStringify(catalog) + "\n");
    expect(readFileSync("../backend/resources/catalog.json", "utf8")).toBe(contents);
    for (const definition of getPrimitives()) {
      const entry = catalog.primitives.find((item: { id: string }) => item.id === definition.id);
      expect(entry).toBeDefined();
      expect(entry.examples).toEqual(definition.examples);
    }
  });
  it("validates examples with independent JSON Schema Draft 2020-12 validation", () => {
    const ajv = new Ajv2020();
    expect(catalog.primitives.length).toBeGreaterThan(0);
    for (const primitive of catalog.primitives) {
      const validate = ajv.compile(primitive.params_schema);
      for (const example of primitive.examples) expect(validate(example.params), JSON.stringify(validate.errors)).toBe(true);
      if (primitive.id === "three-frame") {
        expect(validate({ left: 2 })).toBe(true); // optional default on input
        expect(validate({ left: -1, right: 2 })).toBe(false);
        expect(validate({ left: 1, right: 11 })).toBe(false);
      }
    }
  });
});
