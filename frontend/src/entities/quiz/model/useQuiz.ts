'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient } from '@/shared/api/client';
import { unwrap } from '@/shared/api/errors';
import type { components } from '@/shared/api/schema';

export const QUIZ_QUERY_KEY = ['quiz'] as const;

type PublicQuiz = NonNullable<components['schemas']['PartContentOut']['quizzes']>[number];
type QuizOption = components['schemas']['ChoiceOption'];

interface QuestionPrompt {
  id: string;
  text: string;
}

export type QuizQuestion = QuestionPrompt & (
  | { type: 'single_choice' | 'multiple_choice'; options: QuizOption[] }
  | { type: 'ordering'; items: QuizOption[] }
  | { type: 'numeric'; unit?: string | null }
);

export interface Quiz {
  part_id: string;
  document_id: string;
  questions: QuizQuestion[];
}

export type QuizAnswerValue = components['schemas']['QuizAttemptRequest']['answer'];

export interface QuizAnswer {
  question_id: string;
  answer: QuizAnswerValue;
}

interface QuizSubmitRequest {
  answers: QuizAnswer[];
}

export interface QuizResult {
  score: number;
  total: number;
  percentage: number;
  passed: boolean;
  answers: QuizAnswerResult[];
}

export type QuizAnswerResult = components['schemas']['QuizAttemptResponse'] & {
  question_id: string;
  submitted_answer: QuizAnswerValue;
};

function mapQuizToQuestion(quiz: PublicQuiz): QuizQuestion {
  const prompt = { id: quiz.key, text: quiz.prompt };

  switch (quiz.type) {
    case 'single_choice':
    case 'multiple_choice':
      return { ...prompt, type: quiz.type, options: quiz.options };
    case 'ordering':
      return { ...prompt, type: quiz.type, items: quiz.items };
    case 'numeric':
      return { ...prompt, type: quiz.type, unit: quiz.unit };
  }
}

export function useQuiz(partId: string | null) {
  return useQuery({
    queryKey: [...QUIZ_QUERY_KEY, partId],
    enabled: !!partId,
    queryFn: async () => {
      if (!partId) throw new Error('Part ID is required');
      const part = await unwrap(apiClient.GET('/api/v1/parts/{part_id}', {
        params: { path: { part_id: partId } },
      }));
      const questions = (part.content?.quizzes ?? []).map(mapQuizToQuestion);
      return { part_id: partId, document_id: part.document_id, questions };
    },
  });
}

export function useSubmitQuiz() {
  return useMutation({
    mutationFn: async ({
      partId,
      body,
    }: {
      partId: string;
      body: QuizSubmitRequest;
    }) => {
      const results: QuizAnswerResult[] = [];

      for (const { question_id, answer } of body.answers) {
        const attempt = await unwrap(apiClient.POST('/api/v1/quiz-attempts', {
          body: { part_id: partId, quiz_key: question_id, answer },
        }));

        results.push({ ...attempt, question_id, submitted_answer: answer });
      }

      const total = results.length;
      const correct = results.filter((answer) => answer.is_correct).length;
      const percentage = total > 0 ? Math.round((correct / total) * 100) : 0;

      return {
        score: correct,
        total,
        percentage,
        passed: percentage >= 60,
        answers: results,
      };
    },
  });
}
