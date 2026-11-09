import { useArgs } from "@storybook/preview-api";
import type { Meta, StoryObj } from "@storybook/react";

import { Slider } from "./Slider";

const meta = { component: Slider, title: "UI/Slider" } satisfies Meta<typeof Slider>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: { id: "speed", label: "Speed", max: 100, min: 0, step: 1, onChange: () => undefined, value: 50 },
  render: function Render(args) {
    const [, updateArgs] = useArgs();
    return <Slider {...args} onChange={(value) => { args.onChange(value); updateArgs({ value }); }} />;
  },
};
