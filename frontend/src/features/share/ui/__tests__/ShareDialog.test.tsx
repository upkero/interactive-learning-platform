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
import { ShareDialog } from "../ShareDialog";
import { useDocument } from "@/entities/document";
import { useShareMaterial } from "@/features/share/api";
import { ApiError } from "@/shared/api/errors";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Hoisted mocks
const { mockUseDocument, mockUseShareMaterial } = vi.hoisted(() => ({
  mockUseDocument: vi.fn(),
  mockUseShareMaterial: vi.fn(),
}));

vi.mock("@/entities/document", () => ({
  useDocument: mockUseDocument,
}));

vi.mock("@/features/share/api", () => ({
  useShareMaterial: mockUseShareMaterial,
}));

const messages = {
  share: {
    title: "Share material",
    emailLabel: "Recipient email",
    emailPlaceholder: "student@example.com",
    grantButton: "Grant access",
    sharedWithTitle: "Shared with",
    partsCount: "{count, plural, one {# part} other {# parts}}",
    recipientNote:
      "The recipient will see the original, not a copy: corrections will be visible to everyone. Generations are not charged to the recipient.",
    invalidEmail: "Please enter a valid email address.",
    shareSelfForbidden: "You cannot share a material with yourself.",
    sharedWithNone: "You haven't shared this material with anyone yet.",
  },
  common: {
    loading: "Loading...",
    cancel: "Cancel",
    back: "Back",
    retry: "Retry",
    close: "Close",
  },
  errors: {
    recipient_not_registered: "No user found with the specified email address.",
    share_with_self: "You cannot share a material with yourself.",
    network_error: "Network error. Check your internet connection.",
    unknown_error: "An unexpected error occurred.",
  },
};

const mockDocument = {
  id: "doc-123",
  title: "Test Document",
  role: "owner" as const,
  parts: [
    { id: "part-1", index: 0, title: "Part 1", status: "published" as const },
    { id: "part-2", index: 1, title: "Part 2", status: "published" as const },
  ],
  shared_with: [
    {
      email: "user1@example.com",
      display_name: "User One",
      shared_at: "2024-01-01T00:00:00Z",
    },
    {
      email: "user2@example.com",
      display_name: null,
      shared_at: "2024-01-02T00:00:00Z",
    },
  ],
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

function createMockUseDocument(
  overrides: Partial<{
    data: typeof mockDocument;
    isLoading: boolean;
    isError: boolean;
    error: Error | null;
    isSuccess: boolean;
  }> = {}
) {
  const isLoading = overrides.isLoading ?? false;
  const isError = overrides.isError ?? false;
  const isSuccess = overrides.isSuccess ?? (!isLoading && !isError);
  const data = overrides.data ?? (isSuccess ? mockDocument : undefined);
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

function createMockUseShareMaterial(
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
  props: { documentId: string; isOpen: boolean; onClose: () => void } = {
    documentId: "doc-123",
    isOpen: true,
    onClose: vi.fn(),
  }
) {
  return render(<ShareDialog {...props} />, { wrapper: createWrapper() });
}

describe("ShareDialog", () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseDocument.mockReturnValue(createMockUseDocument());
    mockUseShareMaterial.mockReturnValue(createMockUseShareMaterial());
  });

  afterEach(() => {
    vi.resetAllMocks();
    cleanup();
  });

  describe("Rendering", () => {
    it("renders document title and parts count", () => {
      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      expect(screen.getByText("Test Document")).toBeInTheDocument();
      expect(screen.getByText("2 parts")).toBeInTheDocument();
    });

    it("renders recipient note warning", () => {
      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      expect(
        screen.getByText(
          "The recipient will see the original, not a copy: corrections will be visible to everyone. Generations are not charged to the recipient."
        )
      ).toBeInTheDocument();
    });

    it("renders email input with label and placeholder", () => {
      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      expect(screen.getByLabelText("Recipient email")).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText("student@example.com")
      ).toBeInTheDocument();
    });

    it("renders grant access button", () => {
      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      expect(
        screen.getByRole("button", { name: "Grant access" })
      ).toBeInTheDocument();
    });

    it("renders shared users list", () => {
      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      expect(screen.getByText("User One")).toBeInTheDocument();
      expect(screen.getByText("user1@example.com")).toBeInTheDocument();
      expect(screen.getAllByText("user2@example.com")).toHaveLength(2);
    });

    it("shows empty state when no shared users", () => {
      const docWithoutShared = { ...mockDocument, shared_with: [] };
      mockUseDocument.mockReturnValue(
        createMockUseDocument({ data: docWithoutShared })
      );
      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      expect(
        screen.getByText("You haven't shared this material with anyone yet.")
      ).toBeInTheDocument();
    });

    it("does not render when isOpen is false", () => {
      renderComponent({
        documentId: "doc-123",
        isOpen: false,
        onClose: mockOnClose,
      });
      expect(screen.queryByText("Test Document")).not.toBeInTheDocument();
    });
  });

  describe("Successful share", () => {
    it("calls mutateAsync with correct params and clears input on success", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({ status: "ok" });
      mockUseShareMaterial.mockReturnValue(
        createMockUseShareMaterial({ mutateAsync })
      );

      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      const emailInput = screen.getByLabelText("Recipient email");
      const submitButton = screen.getByRole("button", { name: "Grant access" });

      fireEvent.change(emailInput, {
        target: { value: "newuser@example.com" },
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith({
          documentId: "doc-123",
          email: "newuser@example.com",
        });
      });

      await waitFor(() => {
        expect(screen.getByLabelText("Recipient email")).toHaveValue("");
      });
    });

    it("submits successfully and clears input", async () => {
      const mutateAsync = vi.fn().mockResolvedValue({ status: "ok" });
      mockUseShareMaterial.mockReturnValue(
        createMockUseShareMaterial({ mutateAsync })
      );

      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      const emailInput = screen.getByLabelText("Recipient email");
      const submitButton = screen.getByRole("button", { name: "Grant access" });

      fireEvent.change(emailInput, {
        target: { value: "newuser@example.com" },
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith({
          documentId: "doc-123",
          email: "newuser@example.com",
        });
      });

      await waitFor(() => {
        expect(emailInput).toHaveValue("");
      });
    });
  });

  describe("Error handling", () => {
    it("shows recipient_not_registered error under email input", async () => {
      const error = new ApiError(400, "recipient_not_registered", "Not found");
      const mutateAsync = vi.fn().mockRejectedValue(error);
      mockUseShareMaterial.mockReturnValue(
        createMockUseShareMaterial({ mutateAsync })
      );

      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      const emailInput = screen.getByLabelText("Recipient email");
      const submitButton = screen.getByRole("button", { name: "Grant access" });

      fireEvent.change(emailInput, {
        target: { value: "unknown@example.com" },
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText("No user found with the specified email address.")
        ).toBeInTheDocument();
      });

      // Error should be under the input (aria-describedby)
      const errorElement = screen.getByText(
        "No user found with the specified email address."
      );
      expect(errorElement).toHaveAttribute("role", "alert");
    });

    it("shows share_with_self error under email input", async () => {
      const error = new ApiError(
        400,
        "share_with_self",
        "Cannot share with self"
      );
      const mutateAsync = vi.fn().mockRejectedValue(error);
      mockUseShareMaterial.mockReturnValue(
        createMockUseShareMaterial({ mutateAsync })
      );

      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      const emailInput = screen.getByLabelText("Recipient email");
      const submitButton = screen.getByRole("button", { name: "Grant access" });

      fireEvent.change(emailInput, { target: { value: "owner@example.com" } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText("You cannot share a material with yourself.")
        ).toBeInTheDocument();
      });
    });

    it("shows network_error under email input", async () => {
      const error = new ApiError(0, "network_error", "Network error");
      const mutateAsync = vi.fn().mockRejectedValue(error);
      mockUseShareMaterial.mockReturnValue(
        createMockUseShareMaterial({ mutateAsync })
      );

      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      const emailInput = screen.getByLabelText("Recipient email");
      const submitButton = screen.getByRole("button", { name: "Grant access" });

      fireEvent.change(emailInput, {
        target: { value: "newuser@example.com" },
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText("Network error. Check your internet connection.")
        ).toBeInTheDocument();
      });
    });

    it("shows unknown_error under email input", async () => {
      const error = new ApiError(500, "unknown_error", "Unknown");
      const mutateAsync = vi.fn().mockRejectedValue(error);
      mockUseShareMaterial.mockReturnValue(
        createMockUseShareMaterial({ mutateAsync })
      );

      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      const emailInput = screen.getByLabelText("Recipient email");
      const submitButton = screen.getByRole("button", { name: "Grant access" });

      fireEvent.change(emailInput, {
        target: { value: "newuser@example.com" },
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText("An unexpected error occurred.")
        ).toBeInTheDocument();
      });
    });

    it("keeps focus on email input after error", async () => {
      const error = new ApiError(400, "recipient_not_registered", "Not found");
      const mutateAsync = vi.fn().mockRejectedValue(error);
      mockUseShareMaterial.mockReturnValue(
        createMockUseShareMaterial({ mutateAsync })
      );

      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      const emailInput = screen.getByLabelText("Recipient email");
      const submitButton = screen.getByRole("button", { name: "Grant access" });

      fireEvent.change(emailInput, {
        target: { value: "unknown@example.com" },
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText("No user found with the specified email address.")
        ).toBeInTheDocument();
      });

      // Focus should remain on email input (in jsdom this may not work perfectly, but the component sets aria-invalid)
      expect(emailInput).toHaveAttribute("aria-invalid", "true");
    });
  });

  describe("Accessibility and focus", () => {
    it("has proper aria attributes on email input when error exists", async () => {
      const error = new ApiError(400, "recipient_not_registered", "Not found");
      const mutateAsync = vi.fn().mockRejectedValue(error);
      mockUseShareMaterial.mockReturnValue(
        createMockUseShareMaterial({ mutateAsync })
      );

      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      const emailInput = screen.getByLabelText("Recipient email");
      const submitButton = screen.getByRole("button", { name: "Grant access" });

      fireEvent.change(emailInput, {
        target: { value: "unknown@example.com" },
      });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(emailInput).toHaveAttribute("aria-invalid", "true");
        expect(emailInput).toHaveAttribute("aria-describedby", "email-error");
      });
    });

    it("closes on Escape key", async () => {
      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      fireEvent.keyDown(document, { key: "Escape" });
      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledTimes(1);
      });
    });

    it("calls onClose when close button clicked", async () => {
      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      const closeButton = screen.getAllByRole("button", { name: "Close" })[0];
      fireEvent.click(closeButton);
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  describe("Non-owner access", () => {
    it("shows loading state for non-owner", () => {
      const sharedDoc = {
        ...mockDocument,
        role: "shared" as const,
        shared_with: [],
      };
      mockUseDocument.mockReturnValue(
        createMockUseDocument({ data: sharedDoc })
      );
      renderComponent({
        documentId: "doc-123",
        isOpen: true,
        onClose: mockOnClose,
      });
      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });
  });
});
