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
}

export function StepControls({
  currentStep,
  totalSteps,
  isPlaying,
  labels,
  onPrevious,
  onNext,
  onTogglePlayback,
}: StepControlsProps) {
  return (
    <div className={styles.controls}>
      <Button
        disabled={currentStep <= 1}
        label={labels.previous}
        onClick={onPrevious}
        variant="secondary"
      />
      <Button
        label={isPlaying ? labels.pause : labels.play}
        onClick={onTogglePlayback}
      />
      <Button
        disabled={currentStep >= totalSteps}
        label={labels.next}
        onClick={onNext}
        variant="secondary"
      />
      <output aria-live="polite" className={styles.counter}>
        {labels.step(currentStep, totalSteps)}
      </output>
    </div>
  );
}
