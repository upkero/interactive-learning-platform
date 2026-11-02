import { useMemo, type ReactNode } from "react";
import { PrimitiveShell } from "./PrimitiveShell";
import { MAX_FRAMES, MVP_MODES, type Frame, type Labels, type Mode, type PrimitiveProps } from "./types";
import { stableStringify } from "./serialization";

export function createStepPrimitive<Params, F extends Frame>(config: {
  buildFrames: (params: Params) => readonly F[];
  renderFrame: (frame: F, index: number, labels: Labels) => ReactNode;
  modes?: readonly Mode[];
}) {
  return function StepPrimitive({ params, mode, labels, onEvent }: PrimitiveProps<Params>) {
    const paramsKey = stableStringify(params);
    const frames = useMemo(() => config.buildFrames(params), [params]);
    if (!frames.length || frames.length > MAX_FRAMES) throw new Error(`Expected 1–${MAX_FRAMES} frames.`);
    // A new configuration starts a fresh session. Locale/theme changes keep progress.
    return <PrimitiveShell key={`${mode}:${paramsKey}`} frames={frames} labels={labels} mode={mode}
      modes={config.modes ?? MVP_MODES} onEvent={onEvent} renderFrame={config.renderFrame} />;
  };
}
