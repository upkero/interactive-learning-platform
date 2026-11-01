import styles from "./Toggle.module.css";

export interface ToggleProps {
  id: string;
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}

export function Toggle({
  id,
  label,
  checked,
  disabled = false,
  onChange,
}: ToggleProps) {
  return (
    <label className={styles.label} htmlFor={id}>
      <input
        checked={checked}
        className={styles.input}
        disabled={disabled}
        id={id}
        onChange={(event) => onChange(event.currentTarget.checked)}
        role="switch"
        type="checkbox"
      />
      <span aria-hidden="true" className={styles.track} />
      <span>{label}</span>
    </label>
  );
}
