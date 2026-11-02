import type { ComponentType } from "react";
import { z } from "zod";
import { describe, expect, it } from "vitest";

import { assertCatalogSafeSchema, definePrimitive } from "./definePrimitive";
import type { PrimitiveDefinition, PrimitiveProps } from "./types";

interface ExampleParams {
  values: number[];
}

const ExampleComponent: ComponentType<PrimitiveProps<ExampleParams>> = () => null;

const validDefinition: PrimitiveDefinition<ExampleParams> = {
  id: "example-values",
  version: "1.0.0",
  title: "Example values",
  description: "Shows a short list of numeric values when comparing ordered items.",
  paramsSchema: z.object({
    values: z.array(z.number().min(0).max(100)).min(1).max(10),
  }),
  modes: ["watch", "steps"],
  component: ExampleComponent,
  examples: [
    { name: "compare-two", intent: "Compare two numeric values.", mode: "steps", params: { values: [2, 5] } },
    { name: "watch-three", intent: "Watch three values in order.", mode: "watch", params: { values: [1, 3, 8] } },
  ],
  labelKeys: ["common.next", "example-values.caption"],
};

describe("catalog schema guard", () => {
  it.each([
    ["superRefine", z.number().superRefine((value, ctx) => { if (value < 0) ctx.addIssue({ code: "custom", message: "Positive only" }); })],
    ["nested superRefine", z.object({ values: z.array(z.number().superRefine((_value, ctx) => ctx.addIssue({ code: "custom", message: "Rejected" }))) })],
    ["custom", z.custom<number>((value) => typeof value === "number")],
    ["pipe", z.string().pipe(z.string().min(2))],
    ["date", z.date()],
  ])("rejects %s", (_name, schema) => {
    expect(() => assertCatalogSafeSchema(schema)).toThrow();
  });
  it("accepts a JSON Schema-compatible Zod schema", () => {
    expect(() => definePrimitive(validDefinition)).not.toThrow();
  });

  it("rejects refine even though its JSON Schema projection loses the check", () => {
    const schema = z.object({
      values: z.array(z.number()).refine((values) => values.length % 2 === 0),
    });

    expect(() => assertCatalogSafeSchema(schema)).toThrow("unsupported Zod custom");
  });

  it("rejects transform and pipe schemas", () => {
    expect(() => assertCatalogSafeSchema(z.string().transform(Number))).toThrow(
      "unsupported Zod pipe",
    );
  });
});
