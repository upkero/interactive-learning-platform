import { useLayoutEffect, useRef, useState } from "react";
import type { Frame, PrimitiveEvent } from "../types";

/** One committed answer per visit to a question. Wrong answers also unlock Next. */
export function usePredict(
  frame: Frame,
  enabled: boolean,
  onEvent?: (event: PrimitiveEvent) => void
) {
  const question = enabled ? frame.question : undefined;
  const questionId = question?.id;
  const [state, setState] = useState<{
    questionId?: string;
    answeredId: string | null;
  }>({ questionId, answeredId: null });
  const committed = useRef<string | null>(null);
  useLayoutEffect(() => {
    committed.current = null;
  }, [questionId]);
  if (state.questionId !== questionId) {
    setState({ questionId, answeredId: null });
  }
  const answeredId = state.questionId === questionId ? state.answeredId : null;
  return {
    question,
    answeredId,
    correct:
      question && answeredId !== null
        ? answeredId === question.correctId
        : null,
    canAdvance: !question || answeredId !== null,
    answer: (optionId: string) => {
      if (
        !question ||
        committed.current !== null ||
        !question.options.some((option) => option.id === optionId)
      )
        return;
      committed.current = optionId;
      setState({ questionId, answeredId: optionId });
      onEvent?.({
        type: "predict",
        questionId: question.id,
        correct: optionId === question.correctId,
      });
    },
  };
}
