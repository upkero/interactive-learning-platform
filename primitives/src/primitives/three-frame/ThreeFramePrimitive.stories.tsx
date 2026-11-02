import type { Meta, StoryObj } from "@storybook/react";
import { PrimitiveStory } from "../../../.storybook/PrimitiveStory";
import { threeFrame } from ".";

const meta = {
  title: "Primitives/Three frame",
  component: PrimitiveStory,
  args: { definition: threeFrame, example: "add-two" },
  argTypes: {
    definition: { control: false },
    example: { control: "select", options: threeFrame.examples.map((example) => example.name) },
    mode: { control: "inline-radio", options: threeFrame.modes },
    locale: { control: false, description: "Use the locale toolbar to switch all primitive labels." },
    params: { control: "object" },
  },
} satisfies Meta<typeof PrimitiveStory>;
export default meta;
type Story = StoryObj<typeof meta>;

export const AddTwo: Story = {};
export const AddZero: Story = { args: { example: "add-zero" } };
export const AddOne: Story = { args: { example: "add-one" } };
export const InvalidParams: Story = { args: { params: { left: -1, right: 2 } } };
