import { useState } from "react";
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
  render: () => {
    const [currentStep, setCurrentStep] = useState(1);
    const [isPlaying, setIsPlaying] = useState(false);
    const totalSteps = 4;
    return (
      <StepControls
        currentStep={currentStep}
        isPlaying={isPlaying}
        labels={{
          next: "Next",
          pause: "Pause",
          play: "Play",
          previous: "Previous",
          step: (current, total) => `Step ${current} of ${total}`,
        }}
        onNext={() => setCurrentStep((step) => Math.min(step + 1, totalSteps))}
        onPrevious={() => setCurrentStep((step) => Math.max(step - 1, 1))}
        onTogglePlayback={() => setIsPlaying((playing) => !playing)}
        totalSteps={totalSteps}
      />
    );
  },
};
