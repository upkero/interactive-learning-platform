/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
  cleanup,
} from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { QuizRunner } from "../QuizRunner";
import { usePart } from "@/entities/part";
import { useSubmitQuizAttempt } from "@/features/quiz/api";
import { ApiError } from "@/shared/api/errors";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { mockUsePart, mockUseSubmitQuizAttempt } = vi.hoisted(() => ({
  mockUsePart: vi.fn(),
  mockUseSubmitQuizAttempt: vi.fn(),
}));

vi.mock("@/entities/part", () => ({
  usePart: mockUsePart,
}));

vi.mock("@/features/quiz/api", () => ({
  useSubmitQuizAttempt: mockUseSubmitQuizAttempt,
}));

// Mock the navigation module
vi.mock("@/shared/i18n/navigation", () => ({
  useRouter: vi.fn(() => ({ replace: vi.fn(), push: vi.fn() })),
  usePathname: vi.fn(),
  useSearchParams: vi.fn(),
  Link: ({
    children,
    href,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const messages = {
  quiz: {
    title: "Knowledge Check",
    questionProgress: "Question {current} of {total}",
    submitAnswer: "Check answer",
    nextQuestion: "Next question",
    finishQuiz: "Finish quiz",
    backToMaterial: "Back to material",
    correct: "Correct!",
    incorrect: "Incorrect",
    correctAnswer: "Correct answer",
    explanationLabel: "Explanation",
    prevQuestion: "Previous question",
    optionsLabel: "Answer options",
    numericPlaceholder: "Enter a number",
    emptyQuiz: "This section has no quiz questions yet.",
    navigationLabel: "Quiz navigation",
  },
  common: {
    loading: "Loading...",
    retry: "Retry",
    back: "Back",
  },
  errors: {
    unknown_error: "An unexpected error occurred.",
  },
};

const mockPart = {
  id: "part-123",
  title: "Test Part",
  content: {
    quizzes: [
      {
        key: "q1",
        type: "single_choice",
        prompt: "What is 2+2?",
        options: [
          { id: "a", text: "3" },
          { id: "b", text: "4" },
          { id: "c", text: "5" },
        ],
        ref: "ref1",
      },
      {
        key: "q2",
        type: "multiple_choice",
        prompt: "Select even numbers",
        options: [
          { id: "a", text: "1" },
          { id: "b", text: "2" },
          { id: "c", text: "3" },
          { id: "d", text: "4" },
        ],
        ref: "ref2",
      },
    ],
    widgets: {},
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

function createMockUsePart(
  overrides: Partial<{
    data: typeof mockPart;
    isLoading: boolean;
    isError: boolean;
    error: Error | null;
    isSuccess: boolean;
  }> = {}
) {
  const isLoading = overrides.isLoading ?? false;
  const isError = overrides.isError ?? false;
  const isSuccess = overrides.isSuccess ?? (!isLoading && !isError);
  const data = overrides.data ?? (isSuccess ? mockPart : undefined);
  const error = overrides.error ?? null;

  return {
    data,
    isLoading,
    isError,
    error,
    isSuccess,
    isPending: isLoading,
    refetch: vi.fn(),
    status: isLoading ? "pending" : isError ? "error" : "success",
    fetchStatus: "idle",
    failureCount: 0,
    failureReason: null,
    dataUpdatedAt: 0,
    errorUpdatedAt: 0,
    isStale: false,
    isFetching: false,
    isRefetching: false,
    isLoadingError: isError,
    isRefetchError: false,
    isPlaceholderData: false,
    remove: vi.fn(),
    errorUpdateCount: 0,
    isFetched: true,
    isFetchedAfterMount: true,
    isPaused: false,
    isEnabled: true,
  };
}

function createMockUseSubmitQuizAttempt(
  overrides: Partial<{
    mutateAsync: ReturnType<typeof vi.fn>;
    isPending: boolean;
    isError: boolean;
    error: Error | null;
  }> = {}
) {
  let pending = overrides.isPending ?? false;
  const mutateAsync =
    overrides.mutateAsync ?? vi.fn().mockResolvedValue({ status: "ok" });

  const wrappedMutateAsync = vi
    .fn()
    .mockImplementation(async (...args: unknown[]) => {
      pending = true;
      try {
        const result = await mutateAsync(...args);
        pending = false;
        return result;
      } catch (error) {
        pending = false;
        throw error;
      }
    });

  return {
    mutateAsync: wrappedMutateAsync,
    isPending: pending,
    isError: overrides.isError ?? false,
    error: overrides.error ?? null,
    reset: vi.fn(),
    status: pending ? "pending" : overrides.isError ? "error" : "idle",
    isIdle: !pending && !overrides.isError,
    isLoading: pending,
    isSuccess: !pending && !overrides.isError,
    failureCount: 0,
    failureReason: null,
    submittedAt: 0,
    variables: undefined,
    context: undefined,
  };
}

function renderComponent(props: { partId: string } = { partId: "part-123" }) {
  return render(<QuizRunner {...props} />, { wrapper: createWrapper() });
}

describe("QuizRunner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePart.mockReturnValue(createMockUsePart());
    mockUseSubmitQuizAttempt.mockReturnValue(createMockUseSubmitQuizAttempt());
  });

  afterEach(() => {
    vi.resetAllMocks();
    cleanup();
  });

  describe("Loading state", () => {
    it("shows skeleton while loading", () => {
      mockUsePart.mockReturnValue(
        createMockUsePart({ isLoading: true, isSuccess: false })
      );
      renderComponent({ partId: "part-123" });
      expect(screen.getByRole("status")).toBeInTheDocument();
    });
  });

  describe("Error state", () => {
    it("shows error message and retry button", () => {
      const error = new Error("Failed to load");
      mockUsePart.mockReturnValue(
        createMockUsePart({ isLoading: false, isError: true, error })
      );
      renderComponent({ partId: "part-123" });
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(
        screen.getByText("An unexpected error occurred.")
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    });
  });

  describe("Empty state", () => {
    it("shows empty message when no quizzes", () => {
      const emptyPart = {
        ...mockPart,
        content: { ...mockPart.content, quizzes: [] },
      };
      mockUsePart.mockReturnValue(createMockUsePart({ data: emptyPart }));
      renderComponent({ partId: "part-123" });
      expect(
        screen.getByText("This section has no quiz questions yet.")
      ).toBeInTheDocument();
    });
  });

  describe("Quiz rendering", () => {
    it("renders first quiz with progress indicator", () => {
      renderComponent({ partId: "part-123" });
      expect(screen.getByText("Question 1 of 2")).toBeInTheDocument();
      expect(screen.getByText("What is 2+2?")).toBeInTheDocument();
      expect(screen.getByRole("radio", { name: /3/ })).toBeInTheDocument();
    });

    it("shows single choice options", () => {
      renderComponent({ partId: "part-123" });
      expect(screen.getByRole("radio", { name: /3/ })).toBeInTheDocument();
      expect(screen.getByRole("radio", { name: /4/ })).toBeInTheDocument();
      expect(screen.getByRole("radio", { name: /5/ })).toBeInTheDocument();
    });
  });

  describe("Answer submission", () => {
    it("submits single choice answer and shows feedback", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({
        is_correct: true,
        correct_answer: "b",
        explanation: "2+2=4",
        option_explanations: { b: "Correct!" },
      });
      mockUseSubmitQuizAttempt.mockReturnValue(
        createMockUseSubmitQuizAttempt({ mutateAsync })
      );

      renderComponent({ partId: "part-123" });
      const radioB = screen.getByRole("radio", { name: /4/ });
      fireEvent.click(radioB);
      const submitBtn = screen.getByRole("button", { name: "Check answer" });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith({
          partId: "part-123",
          quizKey: "q1",
          answer: "b",
        });
      });

      await waitFor(() => {
        expect(screen.getAllByText("Correct!")[0]).toBeInTheDocument();
        expect(screen.getAllByText("4")[0]).toBeInTheDocument();
      });
    });

    it("navigates to multiple choice quiz", async () => {
      renderComponent({ partId: "part-123" });
      fireEvent.click(screen.getByRole("button", { name: "Next question" }));
      await waitFor(() => {
        expect(screen.getByText("Select even numbers")).toBeInTheDocument();
        expect(screen.getByRole("checkbox", { name: /1/ })).toBeInTheDocument();
        expect(screen.getByRole("checkbox", { name: /2/ })).toBeInTheDocument();
        expect(screen.getByRole("checkbox", { name: /3/ })).toBeInTheDocument();
        expect(screen.getByRole("checkbox", { name: /4/ })).toBeInTheDocument();
      });
    });
  });

  describe("Feedback display", () => {
    it("shows correct feedback after successful submission", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({
        is_correct: true,
        correct_answer: "b",
        explanation: "2+2=4",
        option_explanations: { b: "Correct!" },
      });
      mockUseSubmitQuizAttempt.mockReturnValue(
        createMockUseSubmitQuizAttempt({ mutateAsync })
      );

      renderComponent({ partId: "part-123" });
      const radioB = screen.getByRole("radio", { name: /4/ });
      fireEvent.click(radioB);
      fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

      await waitFor(() => {
        expect(screen.getAllByText("Correct!")[0]).toBeInTheDocument();
        expect(screen.getAllByText("4")[0]).toBeInTheDocument();
      });
    });

    it("shows incorrect feedback after failed submission", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({
        is_correct: false,
        correct_answer: "b",
        explanation: "2+2=4, not 3",
        option_explanations: { a: "3 is incorrect" },
      });
      mockUseSubmitQuizAttempt.mockReturnValue(
        createMockUseSubmitQuizAttempt({ mutateAsync })
      );

      renderComponent({ partId: "part-123" });
      const radioA = screen.getByRole("radio", { name: /3/ });
      fireEvent.click(radioA);
      fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

      await waitFor(() => {
        expect(screen.getByText("Incorrect")).toBeInTheDocument();
        expect(screen.getAllByText("4")[0]).toBeInTheDocument();
      });
    });

    it("disables inputs after submission", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({
        is_correct: true,
        correct_answer: "b",
        explanation: "2+2=4",
        option_explanations: null,
      });
      mockUseSubmitQuizAttempt.mockReturnValue(
        createMockUseSubmitQuizAttempt({ mutateAsync })
      );

      renderComponent({ partId: "part-123" });
      const radioA = screen.getByRole("radio", { name: /3/ });
      fireEvent.click(radioA);
      fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

      await waitFor(() => {
        expect(screen.getByText("Correct!")).toBeInTheDocument();
      });

      const radioC = screen.getByRole("radio", { name: /5/ });
      expect(radioC).toBeDisabled();
    });

    it("prevents changing answer after submission", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({
        is_correct: true,
        correct_answer: "b",
        explanation: "2+2=4",
        option_explanations: null,
      });
      mockUseSubmitQuizAttempt.mockReturnValue(
        createMockUseSubmitQuizAttempt({ mutateAsync })
      );

      renderComponent({ partId: "part-123" });
      const radioA = screen.getByRole("radio", { name: /3/ });
      fireEvent.click(radioA);
      fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

      await waitFor(() => {
        expect(screen.getByText("Correct!")).toBeInTheDocument();
      });

      const radioC = screen.getByRole("radio", { name: /5/ });
      fireEvent.click(radioC);
      // After submission, there should be no submit button to click
      expect(
        screen.queryByRole("button", { name: "Check answer" })
      ).not.toBeInTheDocument();
    });
  });

  describe("Navigation", () => {
    it("navigates between questions", async () => {
      renderComponent({ partId: "part-123" });
      expect(screen.getByText("Question 1 of 2")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Next question" }));
      await waitFor(() => {
        expect(screen.getByText("Question 2 of 2")).toBeInTheDocument();
      });

      fireEvent.click(
        screen.getByRole("button", { name: "Previous question" })
      );
      await waitFor(() => {
        expect(screen.getByText("Question 1 of 2")).toBeInTheDocument();
      });
    });

    it("disables previous button on first question", () => {
      renderComponent({ partId: "part-123" });
      expect(
        screen.getByRole("button", { name: "Previous question" })
      ).toBeDisabled();
    });

    it("shows Finish Quiz on last question", async () => {
      renderComponent({ partId: "part-123" });
      fireEvent.click(screen.getByRole("button", { name: "Next question" }));
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Finish quiz" })
        ).toBeInTheDocument();
      });
    });
  });
});
