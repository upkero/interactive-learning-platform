import { useCallback, useEffect, useState } from "react";

interface PlaybackStepper {
  index: number;
  isLast: boolean;
  next: () => void;
}

export function usePlayback(
  stepper: PlaybackStepper,
  isQuestionFrame: boolean,
  intervalMs = 1200,
) {
  const [isPlaying, setIsPlaying] = useState(false);
  const pause = useCallback(() => setIsPlaying(false), []);
  const play = useCallback(() => {
    if (!stepper.isLast && !isQuestionFrame) setIsPlaying(true);
  }, [isQuestionFrame, stepper.isLast]);
  const toggle = useCallback(() => (isPlaying ? pause() : play()), [isPlaying, pause, play]);

  useEffect(() => {
    if (!isPlaying) return;
    if (stepper.isLast || isQuestionFrame) {
      pause();
      return;
    }
    const timer = window.setTimeout(stepper.next, intervalMs);
    return () => window.clearTimeout(timer);
  }, [intervalMs, isPlaying, isQuestionFrame, pause, stepper]);

  useEffect(() => {
    if (stepper.isLast || isQuestionFrame) pause();
  }, [isQuestionFrame, pause, stepper.isLast]);

  return { isPlaying, pause, play, toggle };
}
