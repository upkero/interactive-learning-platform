"use client";

import { useTranslations } from "next-intl";
import type { ChoiceQuiz } from "../model";
import styles from "./MultipleChoiceInput.module.css";

interface MultipleChoiceInputProps {
  quiz: ChoiceQuiz;
  value: string[];
  onChange: (value: string[]) => void;
  disabled?: boolean;
  error?: string;
}

export function MultipleChoiceInput({
  quiz,
  value,
  onChange,
  disabled,
  error,
}: MultipleChoiceInputProps) {
  const t = useTranslations("quiz");

  const handleToggle = (optionId: string) => {
    if (disabled) return;
    const next = value.includes(optionId)
      ? value.filter((id) => id !== optionId)
      : [...value, optionId];
    onChange(next);
  };

  return (
    <fieldset className={`${styles.fieldset} ${error ? styles.hasError : ""}`}>
      <legend className={styles.legend}>{quiz.prompt}</legend>
      <div
        className={styles.options}
        role="group"
        aria-label={t("optionsLabel")}
      >
        {quiz.options.map((option) => (
          <label
            key={option.id}
            className={`${styles.option} ${value.includes(option.id) ? styles.selected : ""}`}
          >
            <input
              type="checkbox"
              name={`quiz-${quiz.key}`}
              value={option.id}
              checked={value.includes(option.id)}
              onChange={() => {
                if (!disabled) handleToggle(option.id);
              }}
              disabled={disabled}
              className={styles.checkbox}
            />
            <span className={styles.optionText}>{option.text}</span>
          </label>
        ))}
      </div>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}
