import { describe, expect, it } from "vitest";
import { z } from "zod";
import { getPrimitive, getPrimitives, primitiveRegistry } from "./registry";
import {
  assertCatalogSafeSchema,
  definePrimitive,
} from "./core/definePrimitive";
import { MAX_FRAMES, MVP_MODES } from "./core/types";
import en from "./i18n/en.json";
import ru from "./i18n/ru.json";
import { buildFrames } from "./test/fixtures/three-frame/frames";
import { threeFrame } from "./test/fixtures/three-frame";
import { threeFrameLabels } from "./test/fixtures/three-frame/labels";

describe("primitive registry contract", () => {
  it("has entries, unique ids and lookup for every definition", () => {
    const ids = primitiveRegistry.map((primitive) => primitive.id);
    expect(ids).not.toContain(threeFrame.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(getPrimitives().map((primitive) => primitive.id)).toEqual(
      [...ids].sort()
    );
    for (const definition of primitiveRegistry)
      expect(getPrimitive(definition.id)).toBe(definition);
    expect(getPrimitive("not-registered")).toBeUndefined();
  });
  for (const definition of [...primitiveRegistry, threeFrame]) {
    it(`${definition.id}: valid examples, modes, schema, translations and field metadata`, () => {
      expect(() => definePrimitive(definition)).not.toThrow();
      expect(() =>
        assertCatalogSafeSchema(definition.paramsSchema)
      ).not.toThrow();
      expect(definition.modes.some((mode) => MVP_MODES.includes(mode))).toBe(
        true
      );
      for (const key of definition.labelKeys) {
        expect(
          Object.hasOwn(
            {
              ...en,
              ...(definition.id === threeFrame.id ? threeFrameLabels.en : {}),
            },
            key
          )
        ).toBe(true);
        expect(
          Object.hasOwn(
            {
              ...ru,
              ...(definition.id === threeFrame.id ? threeFrameLabels.ru : {}),
            },
            key
          )
        ).toBe(true);
      }
      const schema = z.toJSONSchema(definition.paramsSchema, {
        io: "input",
        unrepresentable: "throw",
      });
      const visit = (node: Record<string, unknown>) => {
        if (node.type === "number" || node.type === "integer") {
          expect(node.minimum ?? node.exclusiveMinimum).toBeTypeOf("number");
          expect(node.maximum ?? node.exclusiveMaximum).toBeTypeOf("number");
        }
        if (node.type === "array") {
          expect(node.minItems).toBeTypeOf("number");
          expect(node.maxItems).toBeTypeOf("number");
        }
        if (node.type === "string")
          expect(
            node.enum ?? (node.const === undefined ? undefined : [node.const])
          ).toBeInstanceOf(Array);
        if (node.properties)
          for (const property of Object.values(
            node.properties as Record<string, Record<string, unknown>>
          )) {
            expect(property.description).toBeTypeOf("string");
            expect(String(property.description).trim().length).toBeGreaterThan(
              0
            );
          }
        for (const child of Object.values(node)) {
          if (Array.isArray(child))
            child.forEach((item) => {
              if (item && typeof item === "object") visit(item);
            });
          else if (child && typeof child === "object")
            visit(child as Record<string, unknown>);
        }
      };
      visit(schema);
    });
  }
  it("builds deterministic, bounded and translated frames for all allowed inputs", () => {
    for (let left = 0; left <= 10; left++)
      for (let right = 0; right <= 10; right++) {
        const frames = buildFrames({ left, right });
        expect(frames).toEqual(buildFrames({ left, right }));
        expect(frames.length).toBeLessThanOrEqual(MAX_FRAMES);
        for (const frame of frames) {
          const keys = [
            frame.captionKey,
            ...(frame.question
              ? [
                  frame.question.promptKey,
                  frame.question.explanationKey!,
                  ...frame.question.options.map((option) => option.labelKey),
                ]
              : []),
          ];
          for (const key of keys) {
            expect(Object.hasOwn({ ...en, ...threeFrameLabels.en }, key)).toBe(
              true
            );
            expect(Object.hasOwn({ ...ru, ...threeFrameLabels.ru }, key)).toBe(
              true
            );
          }
        }
      }
  });
});
