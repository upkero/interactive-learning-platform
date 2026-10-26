import { useState } from "react";
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
  render: () => {
    const [value, setValue] = useState<(typeof modes)[number]["id"]>("watch");
    return <ModeTabs ariaLabel="Learning mode" onChange={setValue} tabs={modes} value={value} />;
  },
};
