"use client";

import { useState, useCallback } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/shared/i18n/navigation";
import { usePart } from "@/entities/part";
import { useSubmitQuizAttempt, type QuizAttemptResponse } from "../api";
import { QuizCard } from "@/entities/quiz";
import { useApiErrorMessage } from "@/shared/api";
import styles from "./QuizRunner.module.css";

interface QuizRunnerProps {
  partId: string;
}

export function QuizRunner({ partId }: QuizRunnerProps) {
  const t = useTranslations("quiz");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");
  const locale = useLocale();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [resultsByKey, setResultsByKey] = useState<
    Record<string, { result: QuizAttemptResponse | undefined; error?: string }>
  >({});
  const [submitErrors, setSubmitErrors] = useState<
    Record<string, string | undefined>
  >({});

  const partQuery = usePart(partId);
  const submitMutation = useSubmitQuizAttempt();

  const part = partQuery.data;
  const quizzes = part?.content?.quizzes ?? [];
  const currentQuiz = quizzes[currentIndex];

  // Get error message for part query error at top level (hook rules)
  const partQueryErrorMessage = useApiErrorMessage(partQuery.error);

  const handleSubmit = useCallback(
    (answer: unknown) => {
      // Get current quiz from latest data to avoid stale closure
      const partData = partQuery.data;
      const quizzesData = partData?.content?.quizzes ?? [];
      const quiz = quizzesData[currentIndex];
      // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
      if (!quiz) return;

      setSubmitErrors((prev) => ({ ...prev, [quiz.key]: undefined }));

      void submitMutation
        .mutateAsync({
          partId,
          quizKey: quiz.key,
          answer: answer as string | string[] | number,
        })
        .then((result) => {
          setResultsByKey((prev) => ({ ...prev, [quiz.key]: { result } }));
          setSubmitErrors((prev) => ({ ...prev, [quiz.key]: undefined }));
        })
        .catch((err: unknown) => {
          // Handle error message without calling hook in callback
          let message = tErrors("unknown_error");
          if (err && typeof err === "object" && "code" in err) {
            const code = (err as Record<string, unknown>).code;
            if (typeof code === "string") {
              message = tErrors(code);
            }
          } else if (
            err instanceof TypeError &&
            err.message.includes("fetch")
          ) {
            message = tErrors("network_error");
          }
          setSubmitErrors((prev) => ({ ...prev, [quiz.key]: message }));
        });
    },
    [currentIndex, partId, partQuery.data, submitMutation, tErrors]
  );

  const handleNext = useCallback(() => {
    if (currentIndex < quizzes.length - 1) {
      setCurrentIndex((prev) => prev + 1);
    }
  }, [currentIndex, quizzes.length]);

  const handlePrev = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
    }
  }, [currentIndex]);

  if (partQuery.isPending) {
    return (
      <div
        className={styles.skeleton}
        role="status"
        aria-label={t("loadError")}
      >
        <div className={styles.skeletonCard} />
        <div className={styles.skeletonCard} />
        <div className={styles.skeletonCard} />
      </div>
    );
  }

  if (partQuery.isError) {
    return (
      <div className={styles.errorState} role="alert">
        <h2 className={styles.errorTitle}>{t("loadError")}</h2>
        <p className={styles.errorMessage}>{partQueryErrorMessage}</p>
        <button
          type="button"
          className={styles.retryBtn}
          onClick={() => void partQuery.refetch()}
        >
          {tCommon("retry")}
        </button>
        <Link href={`/${locale}/parts/${partId}`} className={styles.backLink}>
          {t("backToMaterial")}
        </Link>
      </div>
    );
  }

  if (!part) {
    return (
      <div className={styles.emptyState} role="status">
        <p>{t("emptyQuiz")}</p>
        <Link href={`/${locale}/parts/${partId}`} className={styles.backLink}>
          {t("backToMaterial")}
        </Link>
      </div>
    );
  }

  if (quizzes.length === 0) {
    return (
      <div className={styles.emptyState} role="status">
        <p>{t("emptyQuiz")}</p>
        <Link href={`/${locale}/parts/${partId}`} className={styles.backLink}>
          {t("backToMaterial")}
        </Link>
      </div>
    );
  }

  // currentQuiz is guaranteed to exist here because quizzes.length > 0 and currentIndex is valid
  const currentQuizKey = currentQuiz.key;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const currentResult = resultsByKey[currentQuizKey]?.result;
  const currentError = submitErrors[currentQuizKey];

  const progressPercent = ((currentIndex + 1) / quizzes.length) * 100;

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>{part.title}</h1>
        <nav className={styles.progress} aria-label={t("navigationLabel")}>
          <span className={styles.progressText}>
            {t("questionProgress", {
              current: currentIndex + 1,
              total: quizzes.length,
            })}
          </span>
          <div
            className={styles.progressBar}
            role="progressbar"
            aria-valuenow={currentIndex + 1}
            aria-valuemin={1}
            aria-valuemax={quizzes.length}
          >
            <div
              className={styles.progressFill}
              // eslint-disable-next-line @typescript-eslint/restrict-template-expressions
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </nav>
      </header>

      <main className={styles.main}>
        <QuizCard
          quiz={currentQuiz}
          result={currentResult}
          pending={submitMutation.isPending}
          error={currentError}
          onSubmit={handleSubmit}
        />

        <nav className={styles.navigation} aria-label={t("navigationLabel")}>
          <button
            type="button"
            className={`${styles.navBtn} ${styles.prevBtn}`}
            onClick={handlePrev}
            disabled={currentIndex === 0 || submitMutation.isPending}
          >
            {t("prevQuestion")}
          </button>
          <button
            type="button"
            className={`${styles.navBtn} ${styles.nextBtn}`}
            onClick={handleNext}
            disabled={
              currentIndex === quizzes.length - 1 || submitMutation.isPending
            }
          >
            {currentIndex === quizzes.length - 1
              ? t("finishQuiz")
              : t("nextQuestion")}
          </button>
        </nav>

        <Link href={`/${locale}/parts/${partId}`} className={styles.backLink}>
          {t("backToMaterial")}
        </Link>
      </main>
    </div>
  );
}
