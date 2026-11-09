import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  type ReactNode,
} from "react";
import { t, type Labels } from "./labels";
import { usePlayback } from "./modes/usePlayback";
import { usePredict } from "./modes/usePredict";
import { useStepper } from "./modes/useStepper";
import {
  MAX_FRAMES,
  MVP_MODES,
  type Frame,
  type Mode,
  type PrimitiveEvent,
} from "./types";
import { Button, StepControls } from "../ui";
import styles from "./PrimitiveShell.module.css";

export interface PrimitiveShellProps<F extends Frame> {
  frames: readonly F[];
  labels: Labels;
  mode?: Mode;
  modes?: readonly Mode[];
  onEvent?: (event: PrimitiveEvent) => void;
  renderFrame: (frame: F, index: number, labels: Labels) => ReactNode;
}

export function PrimitiveShell<F extends Frame>(props: PrimitiveShellProps<F>) {
  if (props.frames.length < 1 || props.frames.length > MAX_FRAMES) {
    return <p role="alert">{t(props.labels, "common.invalidFrames")}</p>;
  }
  const mode = props.mode ?? "watch";
  if (!MVP_MODES.includes(mode) || !(props.modes ?? MVP_MODES).includes(mode)) {
    return <p role="alert">{t(props.labels, "common.invalidMode")}</p>;
  }
  return <ValidPrimitiveShell {...props} />;
}

function ValidPrimitiveShell<F extends Frame>({
  frames,
  labels,
  mode = "watch",
  onEvent,
  renderFrame,
}: PrimitiveShellProps<F>) {
  const stepper = useStepper(frames.length);
  const frame = frames[stepper.index];
  const eventHandler = useRef(onEvent);
  useLayoutEffect(() => {
    eventHandler.current = onEvent;
  }, [onEvent]);
  const emit = useCallback(
    (event: PrimitiveEvent) => eventHandler.current?.(event),
    []
  );
  const predict = usePredict(frame, mode === "predict", emit);
  const playback = usePlayback(
    stepper,
    Boolean(predict.question) || mode !== "watch"
  );
  const completed = useRef(false);
  const questionRef = useRef<HTMLFieldSetElement>(null);
  const shellRef = useRef<HTMLElement>(null);
  const autoStarted = useRef(false);

  useEffect(() => {
    const element = shellRef.current;
    if (
      mode !== "watch" ||
      !element ||
      autoStarted.current ||
      typeof IntersectionObserver === "undefined" ||
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    )
      return;
    const observer = new IntersectionObserver((entries) => {
      if (
        entries.some((entry) => entry.isIntersecting) &&
        !autoStarted.current
      ) {
        autoStarted.current = true;
        playback.play();
        observer.disconnect();
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [mode, playback.play]);

  useLayoutEffect(() => {
    if (predict.question && shellRef.current?.contains(document.activeElement))
      questionRef.current
        ?.querySelector<HTMLButtonElement>("button:not(:disabled)")
        ?.focus();
  }, [predict.question?.id]);

  useEffect(() => {
    emit({ type: "step", index: stepper.index, total: frames.length });
  }, [emit, frames.length, stepper.index]);
  useEffect(() => {
    if (stepper.atEnd && predict.canAdvance && !completed.current) {
      completed.current = true;
      emit({ type: "complete" });
    }
  }, [emit, predict.canAdvance, stepper.atEnd]);

  return (
    <section ref={shellRef} className={styles.shell}>
      <div className={styles.panel}>
        <div className={styles.scene}>
          {renderFrame(frame, stepper.index, labels)}
        </div>
        <p aria-live="polite" className={styles.caption}>
          {t(labels, frame.captionKey, frame.captionVars)}
        </p>
        {predict.question && (
          <fieldset ref={questionRef} className={styles.question}>
            <legend>
              {t(
                labels,
                predict.question.promptKey,
                predict.question.promptVars
              )}
            </legend>
            <div className={styles.options}>
              {predict.question.options.map((option) => (
                <Button
                  key={option.id}
                  label={t(labels, option.labelKey)}
                  aria-pressed={predict.answeredId === option.id}
                  disabled={predict.answeredId !== null}
                  onClick={() => predict.answer(option.id)}
                  variant="secondary"
                />
              ))}
            </div>
            <div role="status" aria-live="polite">
              {predict.correct !== null && (
                <>
                  <p>
                    {t(
                      labels,
                      predict.correct ? "common.correct" : "common.incorrect"
                    )}
                  </p>
                  {predict.question.explanationKey && (
                    <p>
                      {t(
                        labels,
                        predict.question.explanationKey,
                        predict.question.promptVars
                      )}
                    </p>
                  )}
                </>
              )}
            </div>
          </fieldset>
        )}
        <StepControls
          currentStep={stepper.index + 1}
          totalSteps={frames.length}
          isPlaying={playback.isPlaying}
          showPlayback={mode === "watch"}
          playbackDisabled={Boolean(predict.question)}
          canAdvance={predict.canAdvance}
          labels={{
            previous: t(labels, "common.back"),
            next: t(labels, "common.next"),
            play: t(labels, "common.play"),
            pause: t(labels, "common.pause"),
            step: (current, total) =>
              t(labels, "common.step", { current, total }),
          }}
          onNext={() => {
            if (predict.canAdvance) {
              playback.pause();
              stepper.next();
            }
          }}
          onPrevious={() => {
            playback.pause();
            stepper.prev();
          }}
          onTogglePlayback={playback.toggle}
        />
      </div>
    </section>
  );
}
