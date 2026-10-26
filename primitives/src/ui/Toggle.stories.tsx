import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react";

import { Toggle } from "./Toggle";

const meta = { component: Toggle, title: "UI/Toggle" } satisfies Meta<typeof Toggle>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: { checked: false, id: "autoplay", label: "Autoplay", onChange: () => undefined },
  render: () => {
    const [checked, setChecked] = useState(false);
    return <Toggle checked={checked} id="autoplay" label="Autoplay" onChange={setChecked} />;
  },
};
