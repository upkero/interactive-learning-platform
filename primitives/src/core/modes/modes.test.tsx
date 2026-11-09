import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import en from "../../i18n/en.json";
import ru from "../../i18n/ru.json";
import { threeFrame } from "../../test/fixtures/three-frame";
import { buildFrames } from "../../test/fixtures/three-frame/frames";
import { threeFrameLabels } from "../../test/fixtures/three-frame/labels";
import { useStepper } from "./useStepper";
import { usePlayback } from "./usePlayback";
import { usePredict } from "./usePredict";
import { createStepPrimitive } from "../createStepPrimitive";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("mode hooks", () => {
  it("clamps boundaries and resets when total changes", () => {
    const { result, rerender } = renderHook(({ total }) => useStepper(total), {
      initialProps: { total: 3 },
    });
    act(() => result.current.prev());
    expect(result.current.index).toBe(0);
    act(() => result.current.goTo(20));
    expect(result.current.index).toBe(2);
    act(() => result.current.next());
    expect(result.current.atEnd).toBe(true);
    rerender({ total: 2 });
    expect(result.current.index).toBe(0);
    act(() => result.current.goTo(-5));
    expect(result.current.atStart).toBe(true);
  });
  it("plays every 1200ms, pauses, stops at the end and cleans timers", () => {
    vi.useFakeTimers();
    const { result, unmount, rerender } = renderHook(() => {
      const stepper = useStepper(3);
      return { stepper, playback: usePlayback(stepper, false) };
    });
    act(() => result.current.playback.play());
    act(() => vi.advanceTimersByTime(600));
    rerender();
    act(() => vi.advanceTimersByTime(600));
    expect(result.current.stepper.index).toBe(1);
    act(() => result.current.playback.pause());
    act(() => vi.advanceTimersByTime(2400));
    expect(result.current.stepper.index).toBe(1);
    act(() => result.current.playback.play());
    act(() => vi.advanceTimersByTime(1200));
    expect(result.current.stepper.index).toBe(2);
    expect(result.current.playback.isPlaying).toBe(false);
    act(() => result.current.stepper.goTo(0));
    act(() => result.current.playback.play());
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
  it("stops at questions and cannot start on a question", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => {
      const stepper = useStepper(3);
      return { stepper, playback: usePlayback(stepper, stepper.index === 1) };
    });
    act(() => result.current.playback.play());
    act(() => vi.advanceTimersByTime(1200));
    expect(result.current.stepper.index).toBe(1);
    expect(result.current.playback.isPlaying).toBe(false);
    act(() => result.current.playback.play());
    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.stepper.index).toBe(1);
  });
  it("blocks before answering, emits once and resets for another question", () => {
    const frame = buildFrames({ left: 2, right: 1 })[1];
    const onEvent = vi.fn();
    const { result, rerender } = renderHook(
      ({ current, enabled }) => usePredict(current, enabled, onEvent),
      { initialProps: { current: frame, enabled: true } }
    );
    expect(result.current.canAdvance).toBe(false);
    act(() => result.current.answer("unknown"));
    expect(result.current.canAdvance).toBe(false);
    act(() => {
      result.current.answer("no");
      result.current.answer("yes");
    });
    expect(result.current.correct).toBe(false);
    expect(result.current.canAdvance).toBe(true);
    expect(onEvent).toHaveBeenCalledExactlyOnceWith({
      type: "predict",
      questionId: "sum-increases",
      correct: false,
    });
    rerender({
      current: { ...frame, question: { ...frame.question!, id: "another" } },
      enabled: true,
    });
    expect(result.current.answeredId).toBeNull();
    expect(result.current.canAdvance).toBe(false);
    act(() => result.current.answer("yes"));
    expect(result.current.correct).toBe(true);
    rerender({ current: frame, enabled: false });
    expect(result.current.canAdvance).toBe(true);
    expect(result.current.question).toBeUndefined();
  });
});

describe("three-frame primitive", () => {
  const Demo = threeFrame.component;
  it("watch mode continues through a frame with an inactive question", () => {
    vi.useFakeTimers();
    render(
      <Demo
        params={{ left: 3, right: 2 }}
        mode="watch"
        labels={{ ...en, ...threeFrameLabels.en }}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    act(() => vi.advanceTimersByTime(1200));
    expect(screen.getByText("Step 2 of 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pause" })).toBeEnabled();
    act(() => vi.advanceTimersByTime(1200));
    expect(screen.getByText("Step 3 of 3")).toBeInTheDocument();
  });
  it("blocks Next, explains answers, resets on return and completes once", () => {
    const onEvent = vi.fn();
    render(
      <Demo
        params={{ left: 3, right: 2 }}
        mode="predict"
        labels={{ ...en, ...threeFrameLabels.en }}
        onEvent={onEvent}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "No" }));
    expect(screen.getByText("Incorrect")).toBeInTheDocument();
    expect(screen.getByText(/Adding 2 to 3 gives 5/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yes" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(
      onEvent.mock.calls.filter(([event]) => event.type === "complete")
    ).toHaveLength(1);
  });
  it("steps manually, resets new params, keeps progress when locale changes", () => {
    const { rerender } = render(
      <Demo
        params={{ left: 3, right: 2 }}
        mode="steps"
        labels={{ ...en, ...threeFrameLabels.en }}
      />
    );
    expect(
      screen.queryByRole("button", { name: "Play" })
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    rerender(
      <Demo
        params={{ left: 3, right: 2 }}
        mode="steps"
        labels={{ ...ru, ...threeFrameLabels.ru }}
      />
    );
    expect(screen.getByText("Шаг 2 из 3")).toBeInTheDocument();
    rerender(
      <Demo
        params={{ left: 4, right: 0 }}
        mode="steps"
        labels={{ ...en, ...threeFrameLabels.en }}
      />
    );
    expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    rerender(
      <Demo
        params={{ left: 4, right: 0 }}
        mode="watch"
        labels={{ ...en, ...threeFrameLabels.en }}
      />
    );
    expect(screen.getByRole("button", { name: "Play" })).toBeEnabled();
  });
  it("rejects unsupported modes and enforces MAX_FRAMES", () => {
    const StepsOnly = createStepPrimitive({
      modes: ["steps"],
      buildFrames,
      Scene: () => null,
    });
    render(
      <StepsOnly
        params={{ left: 1, right: 1 }}
        mode="watch"
        labels={{ ...en, ...threeFrameLabels.en }}
      />
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      en["common.invalidMode"]
    );
    cleanup();
    const TooMany = createStepPrimitive({
      buildFrames: () =>
        Array.from({ length: 201 }, () => ({ captionKey: "common.next" })),
      Scene: () => null,
    });
    render(<TooMany params={{}} mode="steps" labels={en} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      en["common.invalidFrames"]
    );
  });
  it("shows a fallback when frame construction fails or returns no frames", () => {
    const Empty = createStepPrimitive({
      buildFrames: () => [],
      Scene: () => null,
    });
    const Broken = createStepPrimitive({
      buildFrames: () => {
        throw new Error("invalid frames");
      },
      Scene: () => null,
    });
    const { rerender } = render(<Empty params={{}} mode="steps" labels={en} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      en["common.invalidFrames"]
    );
    rerender(<Broken params={{}} mode="steps" labels={en} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      en["common.invalidFrames"]
    );
  });
});
