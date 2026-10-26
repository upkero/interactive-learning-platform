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
  function changeFromKeyboard(key: string) {
    const increment = key === "ArrowRight" || key === "ArrowUp" ? step : -step;
    if (key === "Home") return min;
    if (key === "End") return max;
    if (!["ArrowDown", "ArrowLeft", "ArrowRight", "ArrowUp"].includes(key)) {
      return undefined;
    }
    return Math.min(max, Math.max(min, value + increment));
  }

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
        onKeyDown={(event) => {
          const nextValue = changeFromKeyboard(event.key);
          if (nextValue === undefined) return;
          event.preventDefault();
          onChange(nextValue);
        }}
        step={step}
        type="range"
        value={value}
      />
    </label>
  );
}
