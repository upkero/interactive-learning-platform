import { useCallback, useEffect, useState } from "react";
import type { Stepper } from "./useStepper";

export function usePlayback(
  { index, atEnd, next }: Pick<Stepper, "index" | "atEnd" | "next">,
  isBlocked: boolean,
  intervalMs = 1200
) {
  const [requested, setRequested] = useState(false);
  const blocked = atEnd || isBlocked;
  const isPlaying = requested && !blocked;
  const pause = useCallback(() => setRequested(false), []);
  const play = useCallback(() => {
    if (!blocked) setRequested(true);
  }, [blocked]);
  const toggle = useCallback(() => {
    if (isPlaying) pause();
    else play();
  }, [isPlaying, pause, play]);
  useEffect(() => {
    if (blocked) pause();
  }, [blocked, pause]);
  useEffect(() => {
    if (!isPlaying) return;
    const timer = window.setTimeout(next, intervalMs);
    return () => window.clearTimeout(timer);
  }, [index, intervalMs, isPlaying, next]);
  return { isPlaying, pause, play, toggle };
}
