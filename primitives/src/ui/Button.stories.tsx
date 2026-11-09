import type { Meta, StoryObj } from "@storybook/react";

import { Button } from "./Button";

const meta = { component: Button, title: "UI/Button" } satisfies Meta<
  typeof Button
>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {
  args: { label: "Continue", variant: "primary" },
};
export const Secondary: Story = {
  args: { label: "Continue", variant: "secondary" },
};
export const Ghost: Story = { args: { label: "Continue", variant: "ghost" } };
