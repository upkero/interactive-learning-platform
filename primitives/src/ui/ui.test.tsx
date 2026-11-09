import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

import { Button } from "./Button";
import { Slider } from "./Slider";
import { StepControls } from "./StepControls";
import { Toggle } from "./Toggle";

describe("base UI controls", () => {
  it("activates Button with the keyboard", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button label="Continue" onClick={onClick} />);

    await user.tab();
    await user.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("reports native Slider input changes", () => {
    const onChange = vi.fn();
    render(
      <Slider
        id="speed"
        label="Speed"
        max={10}
        min={0}
        onChange={onChange}
        value={5}
      />
    );

    fireEvent.change(screen.getByRole("slider", { name: "Speed" }), {
      target: { value: "6" },
    });
    expect(onChange).toHaveBeenCalledWith(6);
  });

  it("changes Toggle with the Space key", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <Toggle
        checked={false}
        id="autoplay"
        label="Autoplay"
        onChange={onChange}
      />
    );

    await user.tab();
    await user.keyboard(" ");
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("activates StepControls buttons with the keyboard", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();
    render(
      <StepControls
        currentStep={1}
        isPlaying={false}
        labels={{
          next: "Next",
          pause: "Pause",
          play: "Play",
          previous: "Previous",
          step: (current, total) => `Step ${current} of ${total}`,
        }}
        onNext={onNext}
        onPrevious={vi.fn()}
        onTogglePlayback={vi.fn()}
        totalSteps={2}
      />
    );

    await user.tab();
    await user.tab();
    await user.keyboard("{Enter}");
    expect(onNext).toHaveBeenCalledOnce();
  });
});
