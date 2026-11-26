'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';

export const QUIZ_QUERY_KEY = ['quiz'] as const;

export type QuestionType = 'single_choice' | 'multiple_choice';

export interface QuizQuestion {
  id: string;
  type: QuestionType;
  text: string;
  options: QuizOption[];
  explanation?: string;
  key?: string;
  ref?: string;
}

export interface QuizOption {
  id: string;
  text: string;
}

export interface Quiz {
  part_id: string;
  questions: QuizQuestion[];
}

export interface QuizAnswer {
  question_id: string;
  option_ids: string[];
}

export interface QuizSubmitRequest {
  answers: QuizAnswer[];
}

export interface QuizResult {
  score: number;
  total: number;
  percentage: number;
  passed: boolean;
  answers: QuizAnswerResult[];
}

export interface QuizAnswerResult {
  question_id: string;
  selected_option_ids: string[];
  correct_option_ids: string[];
  is_correct: boolean;
  explanation?: string;
}

function mapChoiceQuizToQuestion(quiz: components['schemas']['ChoiceQuiz'] | components['schemas']['OrderingQuiz'] | components['schemas']['NumericQuiz']): QuizQuestion {
  if ('options' in quiz) {
    return {
      id: quiz.key,
      type: quiz.type === 'multiple_choice' ? 'multiple_choice' : 'single_choice',
      text: quiz.prompt,
      options: quiz.options.map((opt) => ({ id: opt.id, text: opt.text })),
      key: quiz.key,
      ref: quiz.ref,
    };
  }
  if ('items' in quiz) {
    // Ordering quiz - treat as single choice for now
    return {
      id: quiz.key,
      type: 'single_choice',
      text: quiz.prompt,
      options: quiz.items.map((item) => ({ id: item.id, text: item.text })),
      key: quiz.key,
      ref: quiz.ref,
    };
  }
  // Numeric quiz
  return {
    id: quiz.key,
    type: 'single_choice',
    text: quiz.prompt,
    options: [],
    key: quiz.key,
    ref: quiz.ref,
  };
}

export function useQuiz(partId: string | null) {
  return useQuery({
    queryKey: [...QUIZ_QUERY_KEY, partId],
    enabled: !!partId,
    queryFn: async () => {
      if (!partId) throw new Error('Part ID is required');
      const { data, response } = await apiClient.GET('/api/v1/parts/{part_id}', {
        params: { path: { part_id: partId } },
      });
      if (!response.ok || !data) throw new Error('Failed to load part');
      const part = data;
      const quizzes = part.content?.quizzes ?? [];
      const questions = quizzes.map((quiz) => mapChoiceQuizToQuestion(quiz));
      return { part_id: partId, questions };
    },
  });
}

export function useSubmitQuiz() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      partId,
      body,
    }: {
      partId: string;
      body: QuizSubmitRequest;
    }) => {
      // New API: submit each quiz answer individually to /quiz-attempts
      const partData = await apiClient.GET('/api/v1/parts/{part_id}', {
        params: { path: { part_id: partId } },
      });
      if (!partData.response.ok || !partData.data) throw new Error('Failed to load part');
      const part = partData.data;
      const quizzes = part.content?.quizzes ?? [];

      const results: QuizAnswerResult[] = [];
      let correct = 0;

      for (const answer of body.answers) {
        const quiz = quizzes.find((q) => q.key === answer.question_id);
        if (!quiz) continue;

        const { data: attemptData, response: attemptResponse } = await apiClient.POST('/api/v1/quiz-attempts', {
          body: {
            part_id: partId,
            quiz_key: answer.question_id,
            answer: answer.option_ids.length === 1 ? answer.option_ids[0] : answer.option_ids,
          },
        });

        if (!attemptResponse.ok || !attemptData) {
          throw new Error('Failed to submit quiz attempt');
        }

        const attempt = attemptData;
        const isCorrect = attempt.is_correct;
        if (isCorrect) correct++;

        results.push({
          question_id: answer.question_id,
          selected_option_ids: answer.option_ids,
          correct_option_ids: attempt.correct_answer instanceof Array ? attempt.correct_answer : [String(attempt.correct_answer)],
          is_correct: isCorrect,
          explanation: attempt.explanation ?? undefined,
        });
      }

      const total = body.answers.length;
      const percentage = total > 0 ? Math.round((correct / total) * 100) : 0;

      return {
        score: correct,
        total,
        percentage,
        passed: percentage >= 60,
        answers: results,
      };
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: [...QUIZ_QUERY_KEY, variables.partId, 'result'] });
      void queryClient.invalidateQueries({ queryKey: ['document', variables.partId.split('-')[0], 'parts'] });
    },
  });
}

export function useQuizResult(partId: string | null) {
  return useQuery({
    queryKey: [...QUIZ_QUERY_KEY, partId, 'result'],
    enabled: !!partId,
    queryFn: () => {
      // New API doesn't have a separate result endpoint
      // This hook is kept for compatibility but will return undefined
      // Results are returned directly from useSubmitQuiz mutation
      return undefined as QuizResult | undefined;
    },
  });
}