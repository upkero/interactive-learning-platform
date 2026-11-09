import { z } from "zod";
import { createStepPrimitive } from "../../../core/createStepPrimitive";
import { definePrimitive } from "../../../core/definePrimitive";
import { t } from "../../../core/labels";
import { buildFrames } from "./frames";

const modes = ["watch", "steps", "predict"] as const;
const paramsSchema = z.object({
  left: z
    .number()
    .int()
    .min(0)
    .max(10)
    .meta({ description: "Initial number of counters, from zero to ten." }),
  right: z.number().int().min(0).max(10).default(1).meta({
    description:
      "Number of counters added, from zero to ten. Zero leaves the quantity unchanged.",
  }),
});

export const threeFrame = definePrimitive({
  id: "three-frame",
  version: "1.0.0",
  title: "Three-frame addition demo",
  description:
    "Framework demonstration of adding two non-negative integers from zero to ten. Shows an initial quantity, a prediction about whether it increases, and the resulting sum. Not for negative numbers, fractions, subtraction or general algorithms.",
  paramsSchema,
  modes,
  labelKeys: [
    "common.yes",
    "common.no",
    "three-frame.start",
    "three-frame.predict",
    "three-frame.question",
    "three-frame.explanation",
    "three-frame.result",
    "three-frame.scene",
    "three-frame.initial",
  ],
  examples: [
    {
      name: "add-two",
      intent: "Show how adding two counters changes a group of three.",
      mode: "watch",
      params: { left: 3, right: 2 },
    },
    {
      name: "add-zero",
      intent: "Ask whether adding zero changes a group of four counters.",
      mode: "predict",
      params: { left: 4, right: 0 },
    },
    {
      name: "add-one",
      intent: "Explain adding one to two in separate steps.",
      mode: "steps",
      params: { left: 2, right: 1 },
    },
  ],
  component: createStepPrimitive({
    modes,
    buildFrames,
    renderFrame: (frame, _index, labels) => (
      <div
        role="img"
        aria-label={t(
          labels,
          frame.stage === "start" ? "three-frame.initial" : "three-frame.scene",
          {
            left: frame.left,
            right: frame.right,
            result: frame.stage === "result" ? frame.sum : "?",
          }
        )}
      >
        <p aria-hidden="true">
          {frame.stage === "start"
            ? frame.left
            : `${frame.left} + ${frame.right} = ${frame.stage === "result" ? frame.sum : "?"}`}
        </p>
        <p aria-hidden="true">
          {Array.from(
            { length: frame.stage === "result" ? frame.sum : frame.left },
            () => "●"
          ).join(" ") || "0"}
        </p>
      </div>
    ),
  }),
});
