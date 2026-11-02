import { useCallback, useState } from "react";

export interface Stepper {
  index: number;
  total: number;
  atStart: boolean;
  atEnd: boolean;
  next: () => void;
  prev: () => void;
  goTo: (index: number) => void;
}

export function useStepper(total: number): Stepper {
  if (!Number.isInteger(total) || total < 1) throw new Error("Stepper needs at least one frame.");
  const [state, setState] = useState({ total, index: 0 });
  if (state.total !== total) setState({ total, index: 0 });
  const index = state.total === total ? state.index : 0;
  const goTo = useCallback((value: number) => {
    if (!Number.isFinite(value)) throw new Error("Frame index must be finite.");
    setState({ total, index: Math.max(0, Math.min(total - 1, Math.trunc(value))) });
  }, [total]);
  const next = useCallback(() => setState((current) => ({ total, index: Math.min(total - 1, current.index + 1) })), [total]);
  const prev = useCallback(() => setState((current) => ({ total, index: Math.max(0, current.index - 1) })), [total]);
  return { index, total, atStart: index === 0, atEnd: index === total - 1, next, prev, goTo };
}
