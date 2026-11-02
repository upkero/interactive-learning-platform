import { useEffect, useState, type ReactNode } from "react";

import { t, type Labels } from "./labels";
import { usePlayback } from "./modes/usePlayback";
import { usePredict } from "./modes/usePredict";
import { useStepper } from "./modes/useStepper";
import type { Frame, Mode, PrimitiveEvent } from "./types";
import { Button, ModeTabs, StepControls } from "../ui";
import styles from "./PrimitiveShell.module.css";

interface PrimitiveShellProps<F extends Frame> {
  frames: readonly F[];
  labels: Labels;
  mode?: Extract<Mode, "watch" | "steps" | "predict">;
  onEvent?: (event: PrimitiveEvent) => void;
  renderFrame: (frame: F, index: number) => ReactNode;
}

export function PrimitiveShell<F extends Frame>({ frames, labels, mode: initialMode = "watch", onEvent, renderFrame }: PrimitiveShellProps<F>) {
  const [mode, setMode] = useState(initialMode);
  const stepper = useStepper(frames.length);
  const frame = frames[stepper.index];
  const question = frame?.question;
  const playback = usePlayback(stepper, Boolean(question));
  const predict = usePredict(question?.correctId);

  useEffect(() => { onEvent?.({ type: "step", index: stepper.index, total: frames.length }); }, [frames.length, onEvent, stepper.index]);
  const changeMode = (next: typeof mode) => { playback.pause(); setMode(next); onEvent?.({ type: "mode", mode: next }); };
  const next = () => { playback.pause(); stepper.next(); };
  const previous = () => { playback.pause(); stepper.previous(); };
  const check = () => { const correct = predict.check(); if (question) onEvent?.({ type: "predict", questionId: question.id, correct }); };
  if (!frame) return null;

  return <section className={styles.shell}>
    <ModeTabs ariaLabel={t(labels, "common.mode")} onChange={changeMode} tabs={[{ id: "watch", label: t(labels, "common.watch") }, { id: "steps", label: t(labels, "common.steps") }, { id: "predict", label: t(labels, "common.predict") }]} value={mode} />
    <div className={styles.scene}>{renderFrame(frame, stepper.index)}</div>
    <p aria-live="polite" className={styles.caption}>{t(labels, frame.captionKey, frame.captionVars)}</p>
    <StepControls currentStep={stepper.index + 1} isPlaying={playback.isPlaying} labels={{ previous: t(labels, "common.back"), next: t(labels, "common.next"), play: t(labels, "common.play"), pause: t(labels, "common.pause"), step: (current, total) => t(labels, "common.step", { current, total }) }} onNext={next} onPrevious={previous} onTogglePlayback={playback.toggle} totalSteps={frames.length} />
    {mode === "predict" && question && <aside className={styles.question}><p>{t(labels, question.promptKey, question.promptVars)}</p><div className={styles.options}>{question.options.map((option) => <Button key={option.id} label={t(labels, option.labelKey)} onClick={() => predict.select(option.id)} variant={predict.selectedId === option.id ? "primary" : "secondary"} />)}</div><Button disabled={!predict.selectedId} label={t(labels, "common.check")} onClick={check} />{predict.checked && <p className={styles.feedback}>{predict.correct ? t(labels, "common.correct") : t(labels, "common.incorrect")}</p>}</aside>}
  </section>;
}
