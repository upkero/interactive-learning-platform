/// <reference types="vitest/globals" />
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
  cleanup,
} from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { ReportDialog } from "../ReportDialog";
import { useReportWidget } from "@/features/widget-report/api";
import { ApiError } from "@/shared/api/errors";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Hoisted mocks
const { mockUseReportWidget } = vi.hoisted(() => ({
  mockUseReportWidget: vi.fn(),
}));

vi.mock("@/features/widget-report/api", () => ({
  useReportWidget: mockUseReportWidget,
}));

const messages = {
  report: {
    title: "Report a widget issue",
    reasonLabel: "Report reason",
    reasonBroken: "Widget is broken or fails to render",
    reasonInaccurate: "Factual inaccuracy in content",
    reasonUnhelpful: "Widget does not help explain the topic",
    reasonOther: "Other reason",
    commentLabel: "Comment (optional)",
    commentPlaceholder: "Describe the issue in more detail...",
    submitButton: "Submit report",
    submittedToast: "Thank you, report submitted",
  },
  common: {
    loading: "Loading...",
    cancel: "Cancel",
    back: "Back",
    retry: "Retry",
    close: "Close",
  },
  errors: {
    widget_not_found: "Widget not found.",
    network_error: "Network error. Check your internet connection.",
    unknown_error: "An unexpected error occurred.",
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

function createMockUseReportWidget(
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

function renderComponent(
  props: {
    widgetId: string;
    partId?: string | null;
    isOpen: boolean;
    onClose: () => void;
    onSuccess?: () => void;
  } = {
    widgetId: "widget-123",
    partId: "part-456",
    isOpen: true,
    onClose: vi.fn(),
  }
) {
  return render(<ReportDialog {...props} />, { wrapper: createWrapper() });
}

describe("ReportDialog", () => {
  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseReportWidget.mockReturnValue(createMockUseReportWidget());
  });

  afterEach(() => {
    vi.resetAllMocks();
    cleanup();
  });

  describe("Rendering", () => {
    it("renders title and reason options", () => {
      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      expect(screen.getByText("Report a widget issue")).toBeInTheDocument();
      expect(
        screen.getByText("Widget is broken or fails to render")
      ).toBeInTheDocument();
      expect(
        screen.getByText("Factual inaccuracy in content")
      ).toBeInTheDocument();
      expect(
        screen.getByText("Widget does not help explain the topic")
      ).toBeInTheDocument();
      expect(screen.getByText("Other reason")).toBeInTheDocument();
    });

    it("renders comment textarea with label and placeholder", () => {
      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      expect(screen.getByLabelText("Comment (optional)")).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText("Describe the issue in more detail...")
      ).toBeInTheDocument();
    });

    it("renders cancel and submit buttons", () => {
      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      expect(
        screen.getByRole("button", { name: "Cancel" })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Submit report" })
      ).toBeInTheDocument();
    });

    it("does not render when isOpen is false", () => {
      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: false,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      expect(
        screen.queryByText("Report a widget issue")
      ).not.toBeInTheDocument();
    });
  });

  describe("Form submission", () => {
    it("calls mutateAsync with correct params including reason, part_id, and comment", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({ status: "ok" });
      mockUseReportWidget.mockReturnValue(
        createMockUseReportWidget({ mutateAsync })
      );

      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      // Select "Factual inaccuracy in content" (wrong)
      const wrongRadio = screen.getByLabelText("Factual inaccuracy in content");
      fireEvent.click(wrongRadio);

      // Enter comment
      const commentTextarea = screen.getByLabelText("Comment (optional)");
      fireEvent.change(commentTextarea, {
        target: { value: "This widget shows wrong data" },
      });

      // Submit
      const submitButton = screen.getByRole("button", {
        name: "Submit report",
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith({
          widgetId: "widget-123",
          body: {
            reason: "wrong",
            part_id: "part-456",
            comment: "This widget shows wrong data",
          },
        });
      });
    });

    it("calls mutateAsync with null part_id when not provided", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({ status: "ok" });
      mockUseReportWidget.mockReturnValue(
        createMockUseReportWidget({ mutateAsync })
      );

      renderComponent({
        widgetId: "widget-123",
        partId: undefined,
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      const brokenRadio = screen.getByLabelText(
        "Widget is broken or fails to render"
      );
      fireEvent.click(brokenRadio);

      const submitButton = screen.getByRole("button", {
        name: "Submit report",
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith({
          widgetId: "widget-123",
          body: {
            reason: "broken",
            part_id: null,
            comment: null,
          },
        });
      });
    });

    it("calls mutateAsync with null comment when empty", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({ status: "ok" });
      mockUseReportWidget.mockReturnValue(
        createMockUseReportWidget({ mutateAsync })
      );

      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      const brokenRadio = screen.getByLabelText(
        "Widget is broken or fails to render"
      );
      fireEvent.click(brokenRadio);

      const submitButton = screen.getByRole("button", {
        name: "Submit report",
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith({
          widgetId: "widget-123",
          body: {
            reason: "broken",
            part_id: "part-456",
            comment: null,
          },
        });
      });
    });

    it("calls onSuccess and closes dialog on successful submission", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({ status: "ok" });
      mockUseReportWidget.mockReturnValue(
        createMockUseReportWidget({ mutateAsync })
      );

      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      const brokenRadio = screen.getByLabelText(
        "Widget is broken or fails to render"
      );
      fireEvent.click(brokenRadio);

      const submitButton = screen.getByRole("button", {
        name: "Submit report",
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockOnSuccess).toHaveBeenCalled();
        expect(mockOnClose).toHaveBeenCalled();
      });
    });

    it("calls onSuccess and closes dialog on successful submission", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({ status: "ok" });
      mockUseReportWidget.mockReturnValue(
        createMockUseReportWidget({ mutateAsync })
      );

      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      const brokenRadio = screen.getByLabelText(
        "Widget is broken or fails to render"
      );
      fireEvent.click(brokenRadio);

      const submitButton = screen.getByRole("button", {
        name: "Submit report",
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockOnSuccess).toHaveBeenCalled();
        expect(mockOnClose).toHaveBeenCalled();
      });
    });
  });

  describe("Error handling", () => {
    it("shows widget_not_found error", async () => {
      const error = new ApiError(404, "widget_not_found", "Not found");
      const mutateAsync = vi.fn().mockRejectedValue(error);
      mockUseReportWidget.mockReturnValue(
        createMockUseReportWidget({ mutateAsync })
      );

      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      const brokenRadio = screen.getByLabelText(
        "Widget is broken or fails to render"
      );
      fireEvent.click(brokenRadio);

      const submitButton = screen.getByRole("button", {
        name: "Submit report",
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Widget not found.")).toBeInTheDocument();
      });
    });

    it("shows network_error", async () => {
      const error = new ApiError(0, "network_error", "Network error");
      const mutateAsync = vi.fn().mockRejectedValue(error);
      mockUseReportWidget.mockReturnValue(
        createMockUseReportWidget({ mutateAsync })
      );

      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      const brokenRadio = screen.getByLabelText(
        "Widget is broken or fails to render"
      );
      fireEvent.click(brokenRadio);

      const submitButton = screen.getByRole("button", {
        name: "Submit report",
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText("Network error. Check your internet connection.")
        ).toBeInTheDocument();
      });
    });

    it("shows unknown_error", async () => {
      const error = new ApiError(500, "unknown_error", "Unknown");
      const mutateAsync = vi.fn().mockRejectedValue(error);
      mockUseReportWidget.mockReturnValue(
        createMockUseReportWidget({ mutateAsync })
      );

      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      const brokenRadio = screen.getByLabelText(
        "Widget is broken or fails to render"
      );
      fireEvent.click(brokenRadio);

      const submitButton = screen.getByRole("button", {
        name: "Submit report",
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText("An unexpected error occurred.")
        ).toBeInTheDocument();
      });
    });
  });

  describe("Accessibility and focus", () => {
    it("closes on Escape key", async () => {
      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      fireEvent.keyDown(document, { key: "Escape" });
      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledTimes(1);
      });
    });

    it("calls onClose when close button clicked", async () => {
      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      const closeButton = screen.getAllByRole("button", { name: "Close" })[0];
      fireEvent.click(closeButton);
      expect(mockOnClose).toHaveBeenCalled();
    });

    it("calls onClose when cancel button clicked", async () => {
      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      const cancelButton = screen.getAllByRole("button", { name: "Cancel" })[0];
      fireEvent.click(cancelButton);
      expect(mockOnClose).toHaveBeenCalled();
    });

    it("has proper radio group accessibility", () => {
      renderComponent({
        widgetId: "widget-123",
        partId: "part-456",
        isOpen: true,
        onClose: mockOnClose,
        onSuccess: mockOnSuccess,
      });

      const radioGroup = screen.getAllByRole("radiogroup")[0];
      expect(radioGroup).toBeInTheDocument();
      expect(radioGroup).toHaveAttribute(
        "aria-labelledby",
        "report-reason-label"
      );
    });
  });
});
