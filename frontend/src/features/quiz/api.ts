"use client";

import { useMutation } from "@tanstack/react-query";
import { apiClient, unwrap } from "@/shared/api";
import type { components } from "@/shared/api/schema";

export type QuizAttemptRequest = components["schemas"]["QuizAttemptRequest"];
export type QuizAttemptResponse = components["schemas"]["QuizAttemptResponse"];

export function useSubmitQuizAttempt() {
  return useMutation({
    mutationFn: async ({
      partId,
      quizKey,
      answer,
    }: {
      partId: string;
      quizKey: string;
      answer: string | string[] | number;
    }) => {
      return unwrap(
        apiClient.POST("/api/v1/quiz-attempts", {
          body: {
            part_id: partId,
            quiz_key: quizKey,
            answer,
          },
        })
      );
    },
  });
}
