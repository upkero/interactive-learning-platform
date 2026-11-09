import styles from "./Slider.module.css";

export interface SliderProps {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  disabled?: boolean;
  onChange: (value: number) => void;
}

export function Slider({
  id,
  label,
  value,
  min,
  max,
  step = 1,
  disabled = false,
  onChange,
}: SliderProps) {
  return (
    <label className={styles.field} htmlFor={id}>
      <span className={styles.label}>{label}</span>
      <input
        className={styles.slider}
        disabled={disabled}
        id={id}
        max={max}
        min={min}
        onChange={(event) => onChange(event.currentTarget.valueAsNumber)}
        step={step}
        type="range"
        value={value}
      />
    </label>
  );
}
