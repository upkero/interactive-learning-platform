import { useArgs } from "@storybook/preview-api";
import type { Meta, StoryObj } from "@storybook/react";

import { Toggle } from "./Toggle";

const meta = { component: Toggle, title: "UI/Toggle" } satisfies Meta<
  typeof Toggle
>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    checked: false,
    id: "autoplay",
    label: "Autoplay",
    onChange: () => undefined,
  },
  render: function Render(args) {
    const [, updateArgs] = useArgs();
    return (
      <Toggle
        {...args}
        onChange={(checked) => {
          args.onChange(checked);
          updateArgs({ checked });
        }}
      />
    );
  },
};
