"use client";

import { useTranslations } from "next-intl";
import { useState, useCallback } from "react";
import type { NumericQuiz } from "../model";
import styles from "./NumericInput.module.css";

interface NumericInputProps {
  quiz: NumericQuiz;
  value: number | null;
  onChange: (value: number | null) => void;
  disabled?: boolean;
  error?: string;
}

export function NumericInput({
  quiz,
  value,
  onChange,
  disabled,
  error,
}: NumericInputProps) {
  const t = useTranslations("quiz");
  const [inputValue, setInputValue] = useState(
    value === null ? "" : String(value).replace(".", ",")
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (disabled) return;
      const raw = e.target.value.replace(",", ".");
      setInputValue(raw);
      const num = raw === "" ? null : parseFloat(raw);
      onChange(Number.isNaN(num) ? null : num);
    },
    [disabled, onChange]
  );

  const handleBlur = useCallback(() => {
    if (disabled) return;
    if (inputValue === "" || inputValue === "-") {
      setInputValue("");
      onChange(null);
    }
  }, [disabled, inputValue, onChange]);

  return (
    <fieldset className={`${styles.fieldset} ${error ? styles.hasError : ""}`}>
      <legend className={styles.legend}>
        {quiz.prompt}
        {quiz.unit && <span className={styles.unit}>{quiz.unit}</span>}
      </legend>
      <input
        type="text"
        inputMode="decimal"
        className={styles.input}
        value={inputValue}
        onChange={handleChange}
        onBlur={handleBlur}
        disabled={disabled}
        placeholder={t("numericPlaceholder")}
        aria-describedby={error ? "numeric-error" : undefined}
        aria-invalid={!!error}
      />
      {error && (
        <p id="numeric-error" className={styles.error} role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}
