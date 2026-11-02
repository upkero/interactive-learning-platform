import { useCallback, useState } from "react";

export function useStepper(totalFrames: number) {
  const [index, setIndex] = useState(0);
  const lastIndex = Math.max(0, totalFrames - 1);
  const previous = useCallback(() => setIndex((value) => Math.max(0, value - 1)), []);
  const next = useCallback(() => setIndex((value) => Math.min(lastIndex, value + 1)), [lastIndex]);
  const reset = useCallback(() => setIndex(0), []);

  return { index: Math.min(index, lastIndex), isFirst: index <= 0, isLast: index >= lastIndex, next, previous, reset };
}
