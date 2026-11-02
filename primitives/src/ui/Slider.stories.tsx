import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react";

import { Slider } from "./Slider";

const meta = { component: Slider, title: "UI/Slider" } satisfies Meta<typeof Slider>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: { id: "speed", label: "Speed", max: 100, min: 0, onChange: () => undefined, value: 50 },
  render: () => {
    const [value, setValue] = useState(50);
    return <Slider id="speed" label="Speed" max={100} min={0} onChange={setValue} value={value} />;
  },
};
