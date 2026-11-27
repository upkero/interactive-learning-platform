"use client";

import { useTranslations } from "next-intl";
import type { ChoiceQuiz } from "../model";
import styles from "./SingleChoiceInput.module.css";

interface SingleChoiceInputProps {
  quiz: ChoiceQuiz;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  error?: string;
}

export function SingleChoiceInput({
  quiz,
  value,
  onChange,
  disabled,
  error,
}: SingleChoiceInputProps) {
  const t = useTranslations("quiz");

  const handleChange = (optionId: string) => {
    if (disabled) return;
    onChange(optionId);
  };

  return (
    <fieldset className={`${styles.fieldset} ${error ? styles.hasError : ""}`}>
      <legend className={styles.legend}>{quiz.prompt}</legend>
      <div
        className={styles.options}
        role="radiogroup"
        aria-label={t("optionsLabel")}
      >
        {quiz.options.map((option) => (
          <label
            key={option.id}
            className={`${styles.option} ${value === option.id ? styles.selected : ""}`}
          >
            <input
              type="radio"
              name={`quiz-${quiz.key}`}
              value={option.id}
              checked={value === option.id}
              onChange={() => {
                handleChange(option.id);
              }}
              disabled={disabled}
              className={styles.radio}
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
