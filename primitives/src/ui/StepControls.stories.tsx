import { useArgs } from "@storybook/preview-api";
import type { Meta, StoryObj } from "@storybook/react";

import { StepControls } from "./StepControls";

const meta = { component: StepControls, title: "UI/StepControls" } satisfies Meta<typeof StepControls>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    currentStep: 1,
    isPlaying: false,
    labels: {
      next: "Next",
      pause: "Pause",
      play: "Play",
      previous: "Previous",
      step: (current, total) => `Step ${current} of ${total}`,
    },
    onNext: () => undefined,
    onPrevious: () => undefined,
    onTogglePlayback: () => undefined,
    totalSteps: 4,
  },
  render: function Render(args) {
    const [, updateArgs] = useArgs();
    return (
      <StepControls
        {...args}
        onNext={() => { args.onNext(); updateArgs({ currentStep: Math.min(args.currentStep + 1, args.totalSteps) }); }}
        onPrevious={() => { args.onPrevious(); updateArgs({ currentStep: Math.max(args.currentStep - 1, 1) }); }}
        onTogglePlayback={() => { args.onTogglePlayback(); updateArgs({ isPlaying: !args.isPlaying }); }}
      />
    );
  },
};
