/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { QuizCard } from "../QuizCard";
import { SingleChoiceInput } from "../SingleChoiceInput";
import { MultipleChoiceInput } from "../MultipleChoiceInput";
import { NumericInput } from "../NumericInput";
import { QuizFeedback } from "../QuizFeedback";
import type {
  ChoiceQuiz,
  OrderingQuiz,
  NumericQuiz,
  QuizAttemptResponse,
} from "@/entities/quiz/model";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const messages = {
  quiz: {
    title: "Knowledge Check",
    submitAnswer: "Check answer",
    optionsLabel: "Answer options",
    correct: "Correct!",
    incorrect: "Incorrect",
    correctAnswer: "Correct answer",
    explanationLabel: "Explanation",
    prevQuestion: "Previous question",
    moveUp: "Move up",
    moveDown: "Move down",
    numericPlaceholder: "Enter a number",
  },
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <NextIntlClientProvider locale="en" messages={messages}>
        {children}
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

const singleChoiceQuiz = {
  key: "q1",
  type: "single_choice" as const,
  prompt: "What is 2+2?",
  options: [
    { id: "a", text: "3" },
    { id: "b", text: "4" },
    { id: "c", text: "5" },
  ],
  ref: "ref1",
};

const multipleChoiceQuiz = {
  key: "q2",
  type: "multiple_choice" as const,
  prompt: "Select even numbers",
  options: [
    { id: "a", text: "1" },
    { id: "b", text: "2" },
    { id: "c", text: "3" },
    { id: "d", text: "4" },
  ],
  ref: "ref2",
};

const numericQuiz = {
  key: "q4",
  type: "numeric" as const,
  prompt: "What is 10/2?",
  unit: "units",
  ref: "ref4",
};

const correctSingleChoiceResult: QuizAttemptResponse = {
  is_correct: true,
  correct_answer: "b",
  explanation: "2+2=4",
  option_explanations: { b: "Correct! 2+2=4" },
};

const incorrectSingleChoiceResult: QuizAttemptResponse = {
  is_correct: false,
  correct_answer: "b",
  explanation: "2+2=4, not 3",
  option_explanations: { a: "3 is incorrect" },
};

describe("QuizCard", () => {
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnSubmit.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  function renderQuizCard(props: {
    quiz: any;
    result?: any;
    pending?: boolean;
    error?: string;
  }) {
    return render(
      <QuizCard
        quiz={props.quiz}
        result={props.result}
        pending={props.pending}
        error={props.error}
        onSubmit={mockOnSubmit}
      />,
      { wrapper: createWrapper() }
    );
  }

  describe("SingleChoiceInput", () => {
    it("renders question and options", () => {
      renderQuizCard({ quiz: singleChoiceQuiz });
      expect(screen.getByText("What is 2+2?")).toBeInTheDocument();
      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByText("4")).toBeInTheDocument();
      expect(screen.getByText("5")).toBeInTheDocument();
    });

    it("calls onSubmit with selected option id", async () => {
      renderQuizCard({ quiz: singleChoiceQuiz });
      const radioB = screen.getByRole("radio", { name: /4/ });
      fireEvent.click(radioB);
      const submitBtn = screen.getByRole("button", { name: /Check answer/ });
      fireEvent.click(submitBtn);
      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith("b");
      });
    });

    it("disables inputs when pending is true", () => {
      renderQuizCard({ quiz: singleChoiceQuiz, pending: true });
      const radio = screen.getByRole("radio", { name: /3/ });
      expect(radio).toBeDisabled();
    });
  });

  describe("MultipleChoiceInput", () => {
    it("renders checkboxes for all options", () => {
      renderQuizCard({ quiz: multipleChoiceQuiz });
      expect(screen.getByRole("checkbox", { name: /1/ })).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /2/ })).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /3/ })).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /4/ })).toBeInTheDocument();
    });

    it("renders checkboxes", () => {
      renderQuizCard({ quiz: multipleChoiceQuiz });
      const checkboxB = screen.getByRole("checkbox", { name: /2/ });
      const checkboxD = screen.getByRole("checkbox", { name: /4/ });

      expect(checkboxB).not.toBeChecked();
      expect(checkboxD).not.toBeChecked();
    });

    it("submits array even with single selection", async () => {
      renderQuizCard({ quiz: multipleChoiceQuiz });
      const checkboxB = screen.getByRole("checkbox", { name: /2/ });
      fireEvent.click(checkboxB);
      const submitBtn = screen.getByRole("button", { name: /Check answer/ });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(["b"]);
      });
    });
  });

  describe("NumericInput", () => {
    it("renders input with unit", () => {
      renderQuizCard({ quiz: numericQuiz });
      const input = screen.getByPlaceholderText("Enter a number");
      expect(input).toBeInTheDocument();
      expect(screen.getByText("units")).toBeInTheDocument();
    });

    it("submits number value", async () => {
      renderQuizCard({ quiz: numericQuiz });
      const input = screen.getByPlaceholderText("Enter a number");
      fireEvent.change(input, { target: { value: "5" } });
      const submitBtn = screen.getByRole("button", { name: /Check answer/ });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(5);
      });
    });

    it("handles comma as decimal separator", async () => {
      renderQuizCard({ quiz: numericQuiz });
      const input = screen.getByPlaceholderText("Enter a number");
      fireEvent.change(input, { target: { value: "0,5" } });
      const submitBtn = screen.getByRole("button", { name: /Check answer/ });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(0.5);
      });
    });
  });

  describe("QuizFeedback", () => {
    it("shows correct verdict when is_correct is true", () => {
      renderQuizCard({
        quiz: singleChoiceQuiz,
        result: correctSingleChoiceResult,
      });
      expect(screen.getAllByText("Correct!")[0]).toBeInTheDocument();
      expect(screen.getAllByText("4")[0]).toBeInTheDocument();
      expect(screen.getAllByText("2+2=4")[0]).toBeInTheDocument();
    });

    it("shows incorrect verdict when is_correct is false", () => {
      renderQuizCard({
        quiz: singleChoiceQuiz,
        result: incorrectSingleChoiceResult,
      });
      expect(screen.getAllByText("Incorrect")[0]).toBeInTheDocument();
      expect(screen.getAllByText("4")[0]).toBeInTheDocument();
    });

    it("formats multiple_choice correct answer as comma-separated list", () => {
      const mcResult: QuizAttemptResponse = {
        is_correct: true,
        correct_answer: ["b", "d"],
        explanation: "Even numbers",
        option_explanations: null,
      };
      renderQuizCard({ quiz: multipleChoiceQuiz, result: mcResult });
      expect(screen.getAllByText("2, 4")[0]).toBeInTheDocument();
    });

    it("formats ordering correct answer with arrows", () => {
      const ordResult: QuizAttemptResponse = {
        is_correct: true,
        correct_answer: ["b", "c", "a"],
        explanation: "Order from smallest to largest",
        option_explanations: null,
      };
      const orderingQuiz = {
        key: "q3",
        type: "ordering" as const,
        prompt: "Order from smallest to largest",
        items: [
          { id: "a", text: "3" },
          { id: "b", text: "1" },
          { id: "c", text: "2" },
        ],
        ref: "ref3",
      };
      renderQuizCard({ quiz: orderingQuiz, result: ordResult });
      expect(screen.getAllByText("1. 1 → 2. 2 → 3. 3")[0]).toBeInTheDocument();
    });

    it("formats numeric correct answer with unit", () => {
      const numResult: QuizAttemptResponse = {
        is_correct: true,
        correct_answer: 5,
        explanation: "Division",
        option_explanations: null,
      };
      const numQuiz = { ...numericQuiz, unit: "units" };
      renderQuizCard({ quiz: numQuiz, result: numResult });
      expect(screen.getAllByText("5 units")[0]).toBeInTheDocument();
    });
  });

  describe("Submitted state", () => {
    it("disables inputs after submission", () => {
      renderQuizCard({
        quiz: singleChoiceQuiz,
        result: correctSingleChoiceResult,
      });
      const radios = screen.getAllByRole("radio", { name: /3/ });
      expect(radios[0]).toBeDisabled();
    });

    it("shows feedback after submission", () => {
      renderQuizCard({
        quiz: singleChoiceQuiz,
        result: correctSingleChoiceResult,
      });
      expect(screen.getAllByText("Correct!")[0]).toBeInTheDocument();
    });

    it("does not call onSubmit when already submitted", () => {
      renderQuizCard({
        quiz: singleChoiceQuiz,
        result: correctSingleChoiceResult,
      });
      const radios = screen.getAllByRole("radio", { name: /5/ });
      fireEvent.click(radios[0]);
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });
  });
});
