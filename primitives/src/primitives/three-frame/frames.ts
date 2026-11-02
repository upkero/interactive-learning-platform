import type { Frame } from "../../core/types";

export interface AdditionParams { left: number; right: number }
export interface AdditionFrame extends Frame {
  stage: "start" | "question" | "result";
  left: number;
  right: number;
  sum: number;
}

/** Deterministic three-frame example for the framework, not an MVP teaching module. */
export function buildFrames({ left, right }: AdditionParams): readonly AdditionFrame[] {
  const sum = left + right;
  const values = { left, right, sum };
  return [
    { ...values, stage: "start", captionKey: "three-frame.start", captionVars: values },
    { ...values, stage: "question", captionKey: "three-frame.predict", captionVars: values,
      question: { id: "sum-increases", promptKey: "three-frame.question", promptVars: values,
        options: [{ id: "yes", labelKey: "common.yes" }, { id: "no", labelKey: "common.no" }],
        correctId: right > 0 ? "yes" : "no", explanationKey: "three-frame.explanation" } },
    { ...values, stage: "result", captionKey: "three-frame.result", captionVars: values },
  ];
}
