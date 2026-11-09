import { useLayoutEffect, useRef } from "react";
import { Button } from "./Button";
import styles from "./StepControls.module.css";

export interface StepControlLabels {
  previous: string;
  next: string;
  play: string;
  pause: string;
  step: (currentStep: number, totalSteps: number) => string;
}

export interface StepControlsProps {
  currentStep: number;
  totalSteps: number;
  isPlaying: boolean;
  labels: StepControlLabels;
  onPrevious: () => void;
  onNext: () => void;
  onTogglePlayback: () => void;
  canAdvance?: boolean;
  showPlayback?: boolean;
  playbackDisabled?: boolean;
}

export function StepControls({
  currentStep,
  totalSteps,
  isPlaying,
  labels,
  onPrevious,
  onNext,
  onTogglePlayback,
  canAdvance = true,
  showPlayback = true,
  playbackDisabled = false,
}: StepControlsProps) {
  const previousRef = useRef<HTMLButtonElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const nextHadFocus = useRef(false);
  useLayoutEffect(() => {
    if ((currentStep >= totalSteps || !canAdvance) && nextHadFocus.current) {
      previousRef.current?.focus();
      nextHadFocus.current = false;
    }
  }, [canAdvance, currentStep, totalSteps]);
  return (
    <div className={styles.controls}>
      <Button
        ref={previousRef}
        disabled={currentStep <= 1}
        label={labels.previous}
        onClick={onPrevious}
        variant="secondary"
      />
      {showPlayback && (
        <Button
          label={isPlaying ? labels.pause : labels.play}
          onClick={onTogglePlayback}
          disabled={playbackDisabled || currentStep >= totalSteps}
        />
      )}
      <Button
        disabled={currentStep >= totalSteps || !canAdvance}
        ref={nextRef}
        label={labels.next}
        onFocus={() => {
          nextHadFocus.current = true;
        }}
        onBlur={(event) => {
          if (!event.currentTarget.disabled) nextHadFocus.current = false;
        }}
        onClick={onNext}
        variant="secondary"
      />
      <output aria-live="polite" className={styles.counter}>
        {labels.step(currentStep, totalSteps)}
      </output>
    </div>
  );
}
