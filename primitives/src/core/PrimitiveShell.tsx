import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
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
import { Button, ModeTabs, StepControls } from "../ui";
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
  return <ValidPrimitiveShell {...props} />;
}

function ValidPrimitiveShell<F extends Frame>({
  frames,
  labels,
  mode: initialMode = "watch",
  modes = MVP_MODES,
  onEvent,
  renderFrame,
}: PrimitiveShellProps<F>) {
  const supported = modes.filter((mode) => MVP_MODES.includes(mode));
  if (!supported.length)
    throw new Error("PrimitiveShell requires an MVP mode.");
  const [selectedMode, setMode] = useState(
    supported.includes(initialMode) ? initialMode : supported[0]
  );
  const mode = supported.includes(selectedMode) ? selectedMode : supported[0];
  const id = useId();
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

  useEffect(() => {
    emit({ type: "step", index: stepper.index, total: frames.length });
  }, [emit, frames.length, stepper.index]);
  useEffect(() => {
    if (stepper.atEnd && predict.canAdvance && !completed.current) {
      completed.current = true;
      emit({ type: "complete" });
    }
  }, [emit, predict.canAdvance, stepper.atEnd]);

  function changeMode(next: Mode) {
    playback.pause();
    setMode(next);
    emit({ type: "mode", mode: next });
  }

  return (
    <section className={styles.shell}>
      <ModeTabs
        ariaLabel={t(labels, "common.mode")}
        idPrefix={id}
        panelId={`${id}-panel`}
        onChange={changeMode}
        tabs={supported.map((mode) => ({
          id: mode,
          label: t(labels, `common.${mode}`),
        }))}
        value={mode}
      />
      <div
        role="tabpanel"
        id={`${id}-panel`}
        aria-labelledby={`${id}-${mode}`}
        className={styles.panel}
      >
        <div className={styles.scene}>
          {renderFrame(frame, stepper.index, labels)}
        </div>
        <p aria-live="polite" className={styles.caption}>
          {t(labels, frame.captionKey, frame.captionVars)}
        </p>
        {predict.question && (
          <fieldset className={styles.question}>
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
