// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020";
import { describe, expect, it } from "vitest";
import { getPrimitives } from "../registry";
import { stableStringify } from "./serialization";
import { serializePrimitives } from "./catalog";
import { threeFrame } from "../test/fixtures/three-frame";

describe("published resolver catalog", () => {
  const contents = readFileSync(
    fileURLToPath(new URL("../../dist/catalog.json", import.meta.url)),
    "utf8"
  );
  const catalog = JSON.parse(contents);
  it("sorts primitive IDs by code point independent of locale", () => {
    const items = ["a0", "aa", "a-b"].map((id) => ({ ...threeFrame, id }));
    expect(serializePrimitives(items).map((item) => item.id)).toEqual([
      "a-b",
      "a0",
      "aa",
    ]);
  });
  it("is canonical, synchronized and includes all registered examples", () => {
    expect(contents).toBe(stableStringify(catalog) + "\n");
    expect(
      readFileSync(
        fileURLToPath(
          new URL("../../../backend/resources/catalog.json", import.meta.url)
        ),
        "utf8"
      )
    ).toBe(contents);
    expect(
      catalog.primitives.map((item: { id: string }) => item.id)
    ).not.toContain("three-frame");
    for (const definition of getPrimitives()) {
      const entry = catalog.primitives.find(
        (item: { id: string }) => item.id === definition.id
      );
      expect(entry).toBeDefined();
      expect(entry.examples).toEqual(definition.examples);
    }
  });
  it("validates examples with independent JSON Schema Draft 2020-12 validation", () => {
    const ajv = new Ajv2020();
    for (const primitive of [
      ...catalog.primitives,
      ...serializePrimitives([threeFrame]),
    ]) {
      const validate = ajv.compile(primitive.paramsSchema);
      for (const example of primitive.examples)
        expect(validate(example.params), JSON.stringify(validate.errors)).toBe(
          true
        );
      if (primitive.id === "three-frame") {
        expect(validate({ left: 2 })).toBe(true); // optional default on input
        expect(validate({ left: -1, right: 2 })).toBe(false);
        expect(validate({ left: 1, right: 11 })).toBe(false);
      }
    }
  });
  it("keeps the backend test catalog synchronized with the actual fixture schema", () => {
    const contents = readFileSync(
      fileURLToPath(
        new URL(
          "../../../backend/tests/support/fixtures/seed/three-frame-catalog.json",
          import.meta.url
        )
      ),
      "utf8"
    );
    expect(contents).toBe(
      stableStringify({
        catalogVersion: 1,
        primitives: serializePrimitives([threeFrame]),
      }) + "\n"
    );
  });
});
