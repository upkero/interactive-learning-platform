"use client";

import { useTranslations } from "next-intl";
import type { Quiz, QuizAttemptResponse } from "../model";
import { formatCorrectAnswer, formatOptionExplanations } from "../model";
import styles from "./QuizFeedback.module.css";

interface QuizFeedbackProps {
  quiz: Quiz;
  result: QuizAttemptResponse;
}

export function QuizFeedback({ quiz, result }: QuizFeedbackProps) {
  const t = useTranslations("quiz");
  const correctAnswer = formatCorrectAnswer(quiz, result.correct_answer);
  const optionExplanations = formatOptionExplanations(
    quiz,
    result.option_explanations
  );

  return (
    <div
      className={`${styles.feedback} ${result.is_correct ? styles.correct : styles.incorrect}`}
      role="status"
      aria-live="polite"
    >
      <div className={styles.verdict}>
        {result.is_correct ? (
          <span className={styles.correctText}>{t("correct")}</span>
        ) : (
          <span className={styles.incorrectText}>{t("incorrect")}</span>
        )}
      </div>

      <div className={styles.correctAnswer}>
        <strong>{t("correctAnswer")}:</strong> {correctAnswer}
      </div>

      {result.explanation && (
        <div className={styles.explanation}>
          <strong>{t("explanationLabel")}:</strong> {result.explanation}
        </div>
      )}

      {Object.keys(optionExplanations).length > 0 && (
        <details className={styles.optionExplanations}>
          <summary>
            {t("explanationLabel")} ({t("optionsLabel")})
          </summary>
          <ul className={styles.explanationsList}>
            {Object.entries(optionExplanations).map(
              ([optionId, explanation]) => (
                <li key={optionId} className={styles.explanationItem}>
                  <strong>{optionId}:</strong> {explanation}
                </li>
              )
            )}
          </ul>
        </details>
      )}
    </div>
  );
}
