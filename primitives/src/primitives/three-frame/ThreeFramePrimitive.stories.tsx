import type { Meta, StoryObj } from "@storybook/react";
import { z } from "zod";

import { PrimitiveStory } from "../../../.storybook/PrimitiveStory";
import { createStepPrimitive } from "../../core/createStepPrimitive";
import en from "../../i18n/en.json";

const schema = z.object({ topic: z.string().min(1).max(40) });
const ThreeFramePrimitive = createStepPrimitive({
  frames: (params: { topic: string }) => [
    { captionKey: "demo.first" },
    { captionKey: "demo.second", question: { id: "confirm", promptKey: "demo.question", options: [{ id: "yes", labelKey: "common.yes" }, { id: "no", labelKey: "common.no" }], correctId: "yes" } },
    { captionKey: "demo.third" },
  ],
  renderFrame: (_frame, index) => <strong>{`Frame ${index + 1}`}</strong>,
});
const labels = { ...en, "demo.first": "Introduction", "demo.second": "Prediction point", "demo.third": "Conclusion", "demo.question": "Does this demonstrate the selected topic?" };

const meta = { title: "Primitives/Three frame", component: ThreeFramePrimitive, args: { params: { topic: "Demo" }, mode: "watch", labels }, render: (args) => <PrimitiveStory params={args.params} schema={schema}>{(params) => <ThreeFramePrimitive {...args} params={params} />}</PrimitiveStory> } satisfies Meta<typeof ThreeFramePrimitive>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Watch: Story = {};
export const InvalidParams: Story = { args: { params: { topic: "" } } };
