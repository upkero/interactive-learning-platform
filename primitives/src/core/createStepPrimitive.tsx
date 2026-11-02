import type { ReactNode } from "react";

import { PrimitiveShell } from "./PrimitiveShell";
import type { Frame, PrimitiveProps } from "./types";

export function createStepPrimitive<Params, F extends Frame>(config: {
  frames: (params: Params) => readonly F[];
  renderFrame: (frame: F, index: number) => ReactNode;
}) {
  return function StepPrimitive({ params, mode, labels, onEvent }: PrimitiveProps<Params>) {
    return <PrimitiveShell frames={config.frames(params)} labels={labels} mode={mode === "steps" || mode === "predict" ? mode : "watch"} onEvent={onEvent} renderFrame={config.renderFrame} />;
  };
}
