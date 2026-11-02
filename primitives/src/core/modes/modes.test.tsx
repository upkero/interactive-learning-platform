import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import en from "../../i18n/en.json";
import { createStepPrimitive } from "../createStepPrimitive";

const Demo = createStepPrimitive({
  frames: () => [
    { captionKey: "one" },
    { captionKey: "two", question: { id: "q1", promptKey: "question", options: [{ id: "yes", labelKey: "common.yes" }, { id: "no", labelKey: "common.no" }], correctId: "yes" } },
    { captionKey: "three" },
  ],
  renderFrame: (_frame, index) => <div>Frame {index + 1}</div>,
});

const labels = { ...en, one: "First", two: "Second", three: "Third", question: "Is this correct?" };

describe("shared primitive modes", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("steps through a three-frame primitive and stops playback at a question", async () => {
    vi.useFakeTimers();
    render(<Demo labels={labels} mode="watch" params={{}} />);
    fireEvent.click(screen.getByRole("tab", { name: "Steps" }));
    expect(screen.getByRole("tab", { name: "Steps" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    await act(async () => { vi.advanceTimersByTime(1200); });
    expect(screen.getByText("Frame 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Play" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Frame 3")).toBeInTheDocument();
  });

  it("checks a prediction in predict mode", async () => {
    const user = userEvent.setup();
    render(<Demo labels={labels} mode="predict" params={{}} />);
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("tab", { name: "Predict" }));
    await user.click(screen.getByRole("button", { name: "Yes" }));
    await user.click(screen.getByRole("button", { name: "Check" }));
    expect(screen.getByText("Correct")).toBeInTheDocument();
  });
});
