"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { SingleChoiceInput } from "./SingleChoiceInput";
import { MultipleChoiceInput } from "./MultipleChoiceInput";
import { OrderingInput } from "./OrderingInput";
import { NumericInput } from "./NumericInput";
import { QuizFeedback } from "./QuizFeedback";
import { buildQuizAnswer } from "../model";
import type { Quiz, QuizAttemptResponse } from "../model";
import styles from "./QuizCard.module.css";

interface QuizCardProps {
  quiz: Quiz;
  result?: QuizAttemptResponse;
  pending?: boolean;
  error?: string;
  onSubmit: (answer: unknown) => void;
}

function getInitialValue(quiz: Quiz, result?: QuizAttemptResponse): unknown {
  if (!result) {
    switch (quiz.type) {
      case "single_choice":
        return "";
      case "multiple_choice":
        return [];
      case "ordering":
        return [];
      case "numeric":
        return null;
    }
  }
  return result.correct_answer;
}

export function QuizCard({
  quiz,
  result,
  pending,
  error,
  onSubmit,
}: QuizCardProps) {
  const t = useTranslations("quiz");

  const isSubmitted = Boolean(result);
  const isDisabled = pending || isSubmitted;

  const [currentValue, setCurrentValue] = useState<unknown>(() =>
    getInitialValue(quiz, result)
  );

  const handleChange = (value: unknown) => {
    if (isDisabled) return;
    setCurrentValue(value);
  };

  const handleSubmit = () => {
    if (isSubmitted) return;
    try {
      const answer = buildQuizAnswer(quiz, currentValue);
      onSubmit(answer);
    } catch (err) {
      console.error("Failed to build quiz answer:", err);
    }
  };

  // Update currentValue when result changes (e.g., after submission)
  if (result && !isSubmitted) {
    setCurrentValue(result.correct_answer);
  }

  return (
    <article
      className={`${styles.card} ${isSubmitted ? styles.submitted : ""} ${pending ? styles.pending : ""}`}
    >
      {quiz.type === "single_choice" && (
        <SingleChoiceInput
          quiz={quiz}
          value={currentValue as string}
          onChange={handleChange}
          disabled={isDisabled}
          error={error}
        />
      )}

      {quiz.type === "multiple_choice" && (
        <MultipleChoiceInput
          quiz={quiz}
          value={currentValue as string[]}
          onChange={handleChange}
          disabled={isDisabled}
          error={error}
        />
      )}

      {quiz.type === "ordering" && (
        <OrderingInput
          quiz={quiz}
          value={currentValue as string[]}
          onChange={handleChange}
          disabled={isDisabled}
          error={error}
        />
      )}

      {quiz.type === "numeric" && (
        <NumericInput
          quiz={quiz}
          value={currentValue as number | null}
          onChange={handleChange}
          disabled={isDisabled}
          error={error}
        />
      )}

      {isSubmitted && result && <QuizFeedback quiz={quiz} result={result} />}

      {error && !isSubmitted && (
        <p className={styles.submitError} role="alert">
          {error}
        </p>
      )}

      {!isSubmitted && (
        <button
          type="button"
          className={`${styles.submitBtn} ${pending ? styles.pendingBtn : ""}`}
          onClick={handleSubmit}
          disabled={pending}
        >
          {pending ? t("submitAnswer") : t("submitAnswer")}
        </button>
      )}
    </article>
  );
}
