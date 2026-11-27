'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import {
  type Quiz,
  type QuizAnswerResult,
  type QuizAnswerValue,
  type QuizQuestion,
  type QuizResult,
  useQuiz,
  useSubmitQuiz,
} from '@/entities/quiz';
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
  const [answers, setAnswers] = useState<Partial<Record<string, AnswerDraft>>>({});
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
  const submitAnswers = questions.flatMap((question) => {
    const answer = prepareAnswer(question, answers[question.id]);
    return answer === undefined ? [] : [{ question_id: question.id, answer }];
  });
  const answeredCount = submitAnswers.length;
  const canSubmit = answeredCount === questions.length;

  function handleSubmit() {
    if (!canSubmit || isSubmitting) return;
    setSubmitError(null);

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
        <fieldset
          key={currentQuestion.id}
          className={styles.questionCard}
          aria-labelledby={`question-${currentQuestion.id}`}
          disabled={isSubmitting}
        >
          <legend id={`question-${currentQuestion.id}`} className={styles.questionText}>
            {currentQuestion.text}
          </legend>

          <QuestionInput
            question={currentQuestion}
            draft={answers[currentQuestion.id]}
            onChange={(draft) => { setAnswers((previous) => ({ ...previous, [currentQuestion.id]: draft })); }}
          />
        </fieldset>
      </Surface>

      <nav className={styles.questionNav} aria-label={t('navigationLabel')}>
        <div className={styles.questionDots}>
          {questions.map((question, index) => {
            const questionId = question.id;
            const isAnswered = prepareAnswer(question, answers[questionId]) !== undefined;
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
                  {answerResult && <AnswerReview question={question} result={answerResult} />}
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

type AnswerDraft = string | string[];

function prepareAnswer(question: QuizQuestion, draft: AnswerDraft | undefined): QuizAnswerValue | undefined {
  switch (question.type) {
    case 'single_choice':
      return typeof draft === 'string' ? draft : undefined;
    case 'multiple_choice':
      return Array.isArray(draft) && draft.length > 0 ? draft : undefined;
    case 'ordering':
      return Array.isArray(draft) && draft.length === question.items.length && draft.every(Boolean)
        ? draft
        : undefined;
    case 'numeric': {
      if (typeof draft !== 'string' || draft.trim() === '') return undefined;
      const number = Number(draft);
      return Number.isFinite(number) ? number : undefined;
    }
  }
}

function QuestionInput({
  question,
  draft,
  onChange,
}: {
  question: QuizQuestion;
  draft: AnswerDraft | undefined;
  onChange: (draft: AnswerDraft) => void;
}) {
  const t = useTranslations('quiz');

  if (question.type === 'numeric') {
    return (
      <label className={styles.answerField}>
        <span>{question.unit ? t('numericAnswerWithUnit', { unit: question.unit }) : t('numericAnswer')}</span>
        <input
          type="number"
          step="any"
          value={typeof draft === 'string' ? draft : ''}
          onChange={(event) => { onChange(event.currentTarget.value); }}
          className={styles.answerControl}
        />
      </label>
    );
  }

  if (question.type === 'ordering') {
    const order = Array.isArray(draft) ? draft : question.items.map(() => '');

    return (
      <div className={styles.options}>
        {order.map((itemId, position) => (
          <label key={position} className={styles.answerField}>
            <span>{t('orderingPosition', { position: position + 1 })}</span>
            <select
              value={itemId}
              onChange={(event) => {
                const selectedId = event.currentTarget.value;
                onChange(order.map((id, index) => index === position ? selectedId : id));
              }}
              className={styles.answerControl}
            >
              <option value="">{t('orderingPlaceholder')}</option>
              {question.items.map((item) => (
                <option key={item.id} value={item.id} disabled={item.id !== itemId && order.includes(item.id)}>
                  {item.text}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
    );
  }

  const singleChoice = question.type === 'single_choice';
  const selected = Array.isArray(draft) ? draft : typeof draft === 'string' ? [draft] : [];

  return (
    <div className={styles.options} role={singleChoice ? 'radiogroup' : 'group'} aria-label={t('optionsLabel')}>
      {question.options.map((option) => {
        const checked = selected.includes(option.id);

        return (
          <label key={option.id} className={styles.option}>
            <input
              type={singleChoice ? 'radio' : 'checkbox'}
              name={question.id}
              value={option.id}
              checked={checked}
              onChange={() => {
                if (singleChoice) {
                  onChange(option.id);
                } else {
                  onChange(checked ? selected.filter((id) => id !== option.id) : [...selected, option.id]);
                }
              }}
              className={styles.optionInput}
              aria-label={option.text}
            />
            <span className={styles.optionText}>{option.text}</span>
          </label>
        );
      })}
    </div>
  );
}

function AnswerReview({ question, result }: { question: QuizQuestion; result: QuizAnswerResult }) {
  const t = useTranslations('quiz');
  const { submitted_answer: submitted, correct_answer: correct } = result;

  if (question.type === 'ordering' || question.type === 'numeric') {
    const answers = [
      { label: t('yourAnswer'), value: submitted },
      { label: t('correctAnswer'), value: correct },
    ];

    return (
      <dl className={styles.reviewAnswers}>
        {answers.map(({ label, value }) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>
              {question.type === 'ordering' && Array.isArray(value) && (
                <ol>
                  {value.map((id) => <li key={id}>{question.items.find((item) => item.id === id)?.text ?? id}</li>)}
                </ol>
              )}
              {question.type === 'numeric' && (
                question.unit ? t('numericValueWithUnit', { value: String(value), unit: question.unit }) : String(value)
              )}
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  return (
    <div className={styles.reviewOptions}>
      {question.options.map((option) => {
        const isSelected = Array.isArray(submitted) ? submitted.includes(option.id) : submitted === option.id;
        const isCorrect = Array.isArray(correct) ? correct.includes(option.id) : correct === option.id;

        return (
          <div
            key={option.id}
            className={`${styles.reviewOption} ${isSelected ? styles.selected : ''} ${isCorrect ? styles.correctOption : ''}`}
          >
            <span className={styles.optionMarker}>{isSelected ? '●' : '○'}</span>
            <span className={styles.optionText}>{option.text}</span>
            {isCorrect && <span className={styles.correctBadge}>{t('correct')}</span>}
          </div>
        );
      })}
    </div>
  );
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
