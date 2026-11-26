'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { type Quiz, type QuizResult, useQuiz, useSubmitQuiz } from '@/entities/quiz';
import { ApiError } from '@/shared/api/errors';
import { ActionLink } from '@/shared/ui/action-link/ActionLink';
import { PageShell } from '@/shared/ui/page-shell/PageShell';
import { Surface } from '@/shared/ui/surface/Surface';
import styles from './QuizFeature.module.css';

export function QuizFeature({ partId }: { partId: string }) {
  const t = useTranslations('quiz');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');

  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Partial<Record<string, string[]>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const quizQuery = useQuiz(partId);
  const submitMutation = useSubmitQuiz();

  const quiz = quizQuery.data;
  const result = submitMutation.data;
  const isSubmitting = submitMutation.isPending;
  const materialHref = quiz ? `/documents/${quiz.document_id}` : "/materials";

  // Loading state
  if (quizQuery.isPending) {
    return (
      <PageShell title={t('title')} description={t('questionProgress', { current: 1, total: 1 })}>
        <QuizSkeleton />
      </PageShell>
    );
  }

  // Error state
  if (quizQuery.isError) {
    const message = quizQuery.error instanceof ApiError
      ? tErrors(quizQuery.error.code)
      : tErrors('unknown_error');

    return (
      <PageShell title={t('title')}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <h2 className={styles.errorTitle}>{t('loadError')}</h2>
            <p className={styles.errorMessage}>{message}</p>
            <div className={styles.errorActions}>
              <button
                type="button"
                className={`${styles.actionButton} ${styles.primary}`}
                onClick={() => { void quizQuery.refetch(); }}
              >
                {tCommon('retry')}
              </button>
              <ActionLink
                href={materialHref}
                variant="secondary"
                className={styles.actionButton}
              >
                {tCommon('back')}
              </ActionLink>
            </div>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // Empty quiz
  if (!quiz || quiz.questions.length === 0) {
    return (
      <PageShell title={t('title')}>
        <Surface>
          <div className={styles.emptyState} role="status">
            <p>{t('emptyQuiz')}</p>
            <ActionLink
              href={materialHref}
              variant="primary"
            >
              {t('backToMaterial')}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  if (result) {
    return renderResultScreen(quiz, result);
  }

  const questions = quiz.questions;
  const currentQuestion = questions[currentQuestionIndex];
  const isLastQuestion = currentQuestionIndex === questions.length - 1;
  const currentAnswers = answers[currentQuestion.id] ?? [];
  const answeredCount = questions.filter(({ id }) => (answers[id]?.length ?? 0) > 0).length;
  const canSubmit = answeredCount === questions.length;

  function handleOptionChange(optionId: string) {
    const selectedOptions = currentQuestion.type === 'single_choice'
      ? [optionId]
      : currentAnswers.includes(optionId)
        ? currentAnswers.filter((id) => id !== optionId)
        : [...currentAnswers, optionId];
    setAnswers({ ...answers, [currentQuestion.id]: selectedOptions });
  }

  function handleSubmit() {
    if (!canSubmit || isSubmitting) return;
    setSubmitError(null);

    const submitAnswers = questions.map(({ id }) => ({
      question_id: id,
      option_ids: answers[id] ?? [],
    }));

    submitMutation.mutate(
      { partId, body: { answers: submitAnswers } },
      {
        onError: (error) => {
          setSubmitError(tErrors(error instanceof ApiError ? error.code : 'unknown_error'));
        },
      },
    );
  }

  function handleRetryQuiz() {
    submitMutation.reset();
    setAnswers({});
    setCurrentQuestionIndex(0);
    setSubmitError(null);
  }

  return (
    <PageShell
      title={t('title')}
      description={t('questionProgress', { current: currentQuestionIndex + 1, total: questions.length })}
    >
      {submitError && (
        <div className={styles.submitError} role="alert">
          {submitError}
          <button type="button" className={styles.dismissError} onClick={() => { setSubmitError(null); }}>
            {tCommon('close')}
          </button>
        </div>
      )}

      <Surface>
        <div className={styles.progressBar} role="progressbar" aria-valuenow={answeredCount} aria-valuemin={0} aria-valuemax={questions.length}>
          <div className={styles.progressFill} style={{ width: `${String(Math.round((answeredCount / questions.length) * 100))}%` }} />
        </div>
        <div className={styles.progressLabels}>
          <span>{t('answeredLabel', { count: answeredCount })}</span>
          <span>{t('totalLabel', { count: questions.length })}</span>
        </div>
      </Surface>

      <Surface>
        <fieldset className={styles.questionCard} aria-labelledby={`question-${currentQuestion.id}`}>
          <legend id={`question-${currentQuestion.id}`} className={styles.questionText}>
            {currentQuestion.text}
          </legend>

          <div className={styles.options} role="radiogroup" aria-label={t('optionsLabel')}>
            {currentQuestion.options.map((option) => (
              <label key={option.id} className={styles.option}>
                <input
                  type={currentQuestion.type === 'single_choice' ? 'radio' : 'checkbox'}
                  name={currentQuestion.id}
                  value={option.id}
                  checked={currentAnswers.includes(option.id)}
                  onChange={() => { handleOptionChange(option.id); }}
                  className={styles.optionInput}
                  aria-label={option.text}
                />
                <span className={styles.optionText}>{option.text}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </Surface>

      <nav className={styles.questionNav} aria-label={t('navigationLabel')}>
        <div className={styles.questionDots}>
          {questions.map(({ id: questionId }, index) => {
            const isAnswered = (answers[questionId]?.length ?? 0) > 0;
            return (
              <button
                key={questionId}
                type="button"
                className={`${styles.questionDot} ${index === currentQuestionIndex ? styles.active : ''} ${isAnswered ? styles.answered : ''}`}
                onClick={() => { setCurrentQuestionIndex(index); }}
                aria-label={t('questionDotLabel', { number: index + 1 })}
                aria-current={index === currentQuestionIndex ? 'step' : undefined}
              />
            );
          })}
        </div>
        <div className={styles.navButtons}>
          <button
            type="button"
            className={`${styles.navButton} ${styles.secondary}`}
            onClick={() => { setCurrentQuestionIndex(currentQuestionIndex - 1); }}
            disabled={currentQuestionIndex === 0}
          >
            {tCommon('back')}
          </button>
          {isLastQuestion ? (
            <button
              type="button"
              className={`${styles.navButton} ${styles.primary}`}
              onClick={handleSubmit}
              disabled={!canSubmit || isSubmitting}
            >
              {isSubmitting ? tCommon('loading') : t('finishQuiz')}
            </button>
          ) : (
            <button
              type="button"
              className={`${styles.navButton} ${styles.primary}`}
              onClick={() => { setCurrentQuestionIndex(currentQuestionIndex + 1); }}
            >
              {t('nextQuestion')}
            </button>
          )}
        </div>
      </nav>
    </PageShell>
  );

  function renderResultScreen(quiz: Quiz, result: QuizResult) {
    return (
      <PageShell
        title={t('title')}
        actions={
          <div className={styles.resultActions}>
            <ActionLink
              href={materialHref}
              variant="secondary"
            >
              {t('backToMaterial')}
            </ActionLink>
            <button
              type="button"
              className={`${styles.actionButton} ${styles.primary}`}
              onClick={handleRetryQuiz}
            >
              {t('retryQuiz')}
            </button>
          </div>
        }
      >
        <div className={`${styles.resultCard} ${result.passed ? styles.passed : styles.failed}`}>
          <Surface>
            <div className={styles.resultHeader}>
              <div className={styles.resultIcon}>
                {result.passed ? '✓' : '✕'}
              </div>
              <h2 className={styles.resultTitle}>
                {result.passed ? t('passed') : t('failed')}
              </h2>
              <p className={styles.resultScore}>
                {t('scoreSummary', { correct: result.score, total: result.total })}
              </p>
              <p className={styles.resultPercentage}>{result.percentage}%</p>
            </div>
          </Surface>
        </div>

        <Surface title={t('reviewTitle')}>
          <div className={styles.reviewList}>
            {quiz.questions.map((question, index) => {
              const answerResult = result.answers.find((a) => a.question_id === question.id);
              const isCorrect = answerResult?.is_correct ?? false;

              return (
                <article key={question.id} className={`${styles.reviewItem} ${isCorrect ? styles.correct : styles.incorrect}`}>
                  <header className={styles.reviewHeader}>
                    <span className={styles.reviewQuestionNumber}>
                      {t('questionLabel', { number: index + 1 })}
                    </span>
                    <span className={`${styles.reviewStatus} ${isCorrect ? styles.statusCorrect : styles.statusIncorrect}`}>
                      {isCorrect ? t('correct') : t('incorrect')}
                    </span>
                  </header>
                  <p className={styles.reviewQuestionText}>{question.text}</p>
                  <div className={styles.reviewOptions}>
                    {question.options.map((option) => {
                      const isSelected = answerResult?.selected_option_ids.includes(option.id) ?? false;
                      const isCorrectOption = answerResult?.correct_option_ids.includes(option.id) ?? false;

                      return (
                        <div
                          key={option.id}
                          className={`${styles.reviewOption} ${isSelected ? styles.selected : ''} ${isCorrectOption ? styles.correctOption : ''}`}
                        >
                          <span className={styles.optionMarker}>
                            {isSelected ? '●' : '○'}
                          </span>
                          <span className={styles.optionText}>{option.text}</span>
                          {isCorrectOption && (
                            <span className={styles.correctBadge}>{t('correct')}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {answerResult?.explanation && (
                    <p className={styles.reviewExplanation}>
                      {t('explanationLabel')}: {answerResult.explanation}
                    </p>
                  )}
                </article>
              );
            })}
          </div>
        </Surface>
      </PageShell>
    );
  }
}

function QuizSkeleton() {
  return (
    <div className={styles.skeleton} role="status" aria-label="Загрузка теста...">
      <Surface>
        <div className={styles.skeletonProgress} />
      </Surface>
      <Surface>
        <div className={styles.skeletonQuestion} />
        <div className={styles.skeletonOptions}>
          <div className={styles.skeletonOption} />
          <div className={styles.skeletonOption} />
          <div className={styles.skeletonOption} />
          <div className={styles.skeletonOption} />
        </div>
      </Surface>
      <div className={styles.skeletonNav} />
    </div>
  );
}
