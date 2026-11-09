import { useArgs } from "@storybook/preview-api";
import type { Meta, StoryObj } from "@storybook/react";

import { ModeTabs } from "./ModeTabs";

const modes = [
  { id: "watch", label: "Watch" },
  { id: "steps", label: "Step by step" },
  { id: "predict", label: "Predict" },
] as const;

const meta = { component: ModeTabs, title: "UI/ModeTabs" } satisfies Meta<typeof ModeTabs>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: { ariaLabel: "Learning mode", onChange: () => undefined, tabs: modes, value: "watch" },
  render: function Render(args) {
    const [, updateArgs] = useArgs();
    return <ModeTabs {...args} onChange={(value) => { args.onChange(value); updateArgs({ value }); }} />;
  },
};
