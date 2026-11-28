"use client";

import type { components } from "@/shared/api/schema";

export type ChoiceQuiz = components["schemas"]["ChoiceQuiz"];
export type OrderingQuiz = components["schemas"]["OrderingQuiz"];
export type NumericQuiz = components["schemas"]["NumericQuiz"];

export type Quiz = ChoiceQuiz | OrderingQuiz | NumericQuiz;

export type QuizAttemptRequest = components["schemas"]["QuizAttemptRequest"];
export type QuizAttemptResponse = components["schemas"]["QuizAttemptResponse"];

export type ChoiceOption = components["schemas"]["ChoiceOption"];

export type QuizType = Quiz["type"];

export interface QuizAnswerInput {
  single_choice: string;
  multiple_choice: string[];
  ordering: string[];
  numeric: number;
}

export function buildQuizAnswer(
  quiz: Quiz,
  userInput: unknown
): QuizAnswerInput[QuizType] {
  switch (quiz.type) {
    case "single_choice": {
      if (typeof userInput !== "string") {
        throw new Error("single_choice answer must be a string");
      }
      return userInput;
    }
    case "multiple_choice": {
      if (!Array.isArray(userInput)) {
        throw new Error("multiple_choice answer must be an array");
      }
      return userInput.map(String);
    }
    case "ordering": {
      if (!Array.isArray(userInput)) {
        throw new Error("ordering answer must be an array");
      }
      return userInput.map(String);
    }
    case "numeric": {
      const num =
        typeof userInput === "number"
          ? userInput
          : parseFloat(String(userInput).replace(",", "."));
      if (Number.isNaN(num)) {
        throw new Error("numeric answer must be a valid number");
      }
      return num;
    }
    default: {
      const _exhaustive: never = quiz;
      throw new Error(`Unknown quiz type: ${String(_exhaustive)}`);
    }
  }
}

export function formatCorrectAnswer(
  quiz: Quiz,
  correctAnswer: QuizAttemptResponse["correct_answer"]
): string {
  switch (quiz.type) {
    case "single_choice": {
      const answerId = String(correctAnswer);
      const option = quiz.options.find((o) => o.id === answerId);
      return option?.text ?? answerId;
    }
    case "multiple_choice": {
      if (!Array.isArray(correctAnswer)) return String(correctAnswer);
      const answers = Array.isArray(correctAnswer)
        ? correctAnswer
        : [String(correctAnswer)];
      return answers
        .map((id) => {
          const option = quiz.options.find((o) => o.id === id);
          return option?.text ?? id;
        })
        .join(", ");
    }
    case "ordering": {
      if (!Array.isArray(correctAnswer)) return String(correctAnswer);
      const answers = Array.isArray(correctAnswer)
        ? correctAnswer
        : [String(correctAnswer)];
      return answers
        .map((id, idx) => {
          const option = quiz.items.find((o) => o.id === id);
          return String(idx + 1) + `. ${option?.text ?? id}`;
        })
        .join(" → ");
    }
    case "numeric": {
      const num = Number(correctAnswer);
      const unit = quiz.unit ? ` ${quiz.unit}` : "";
      return Number.isNaN(num) ? String(correctAnswer) : String(num) + unit;
    }
    default: {
      const _exhaustive: never = quiz;
      throw new Error(`Unknown quiz type: ${String(_exhaustive)}`);
    }
  }
}

export function formatOptionExplanations(
  quiz: Quiz,
  optionExplanations: QuizAttemptResponse["option_explanations"]
): Record<string, string> {
  if (!optionExplanations) return {};

  if (
    typeof optionExplanations === "object" &&
    !Array.isArray(optionExplanations)
  ) {
    return optionExplanations;
  }

  if (Array.isArray(optionExplanations)) {
    const result: Record<string, string> = {};
    optionExplanations.forEach((exp, idx) => {
      let option: ChoiceOption | undefined;
      if (quiz.type === "ordering") {
        option = quiz.items[idx];
      } else if (
        quiz.type === "single_choice" ||
        quiz.type === "multiple_choice"
      ) {
        option = quiz.options[idx];
      }
      if (option) {
        result[option.id] = exp;
      }
    });
    return result;
  }

  return {};
}
