import { useMemo, type ComponentType } from "react";
import { PrimitiveShell } from "./PrimitiveShell";
import {
  MVP_MODES,
  type Frame,
  type SceneProps,
  type Mode,
  type PrimitiveProps,
} from "./types";
import { t } from "./labels";
import { stableStringify } from "./serialization";

export function createStepPrimitive<Params, F extends Frame>(config: {
  buildFrames: (params: Params) => readonly F[];
  Scene: ComponentType<SceneProps<Params, F>>;
  modes?: readonly Mode[];
}) {
  return function StepPrimitive({
    params,
    mode,
    labels,
    onEvent,
  }: PrimitiveProps<Params>) {
    const paramsKey = stableStringify(params);
    const result = useMemo(() => {
      try {
        return { frames: config.buildFrames(params) };
      } catch (error) {
        if (
          import.meta.env?.DEV ||
          (typeof process !== "undefined" &&
            process.env.NODE_ENV === "development")
        )
          console.error("Failed to build primitive frames", error);
        return { frames: null };
      }
      // JSON-equivalent params intentionally share frame data and session identity.
    }, [paramsKey]);
    if (!result.frames)
      return <p role="alert">{t(labels, "common.invalidFrames")}</p>;
    // A new configuration starts a fresh session. Locale/theme changes keep progress.
    return (
      <PrimitiveShell
        key={`${mode}:${paramsKey}`}
        frames={result.frames}
        labels={labels}
        mode={mode}
        modes={config.modes ?? MVP_MODES}
        onEvent={onEvent}
        renderFrame={(frame, index, sceneLabels) => (
          <config.Scene
            frame={frame}
            index={index}
            labels={sceneLabels}
            params={params}
          />
        )}
      />
    );
  };
}
