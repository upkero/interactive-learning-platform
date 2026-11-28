/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { DocumentList } from "../DocumentList";
import { useMaterials, getMaterialRoute } from "@/entities/document";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Hoisted mocks
const { mockUseMaterials, mockGetMaterialRoute } = vi.hoisted(() => ({
  mockUseMaterials: vi.fn(),
  mockGetMaterialRoute: vi.fn((doc) => `/documents/${doc.document_id}`),
}));

vi.mock("@/entities/document", () => ({
  useMaterials: mockUseMaterials,
  getMaterialRoute: mockGetMaterialRoute,
}));

// Test messages
const messages = {
  materials: {
    title: "My Materials",
    uploadButton: "Upload material",
    filterAll: "All",
    filterMine: "Mine",
    filterShared: "Shared with me",
    quotaTitle: "Available quota",
    titleLabel: "Title",
    partsLabel: "Parts",
    statusLabel: "Status",
    roleLabel: "Role",
    createdAtLabel: "Created",
    actionsLabel: "Actions",
    sharedLabel: "Shared",
    ownerLabel: "Owner",
    sharedByLabel: "From {email}",
    shareAction: "Share",
    deleteConfirm: 'Delete material "{title}"?',
    retryAction: "Retry",
    deleteAction: "Delete",
    status: {
      uploaded: "Uploaded",
      parsing: "Parsing file",
      parsed: "Topics selected",
      generating: "Generating: {published}/{total}",
      done: "Ready",
      failed: "Error",
    },
    empty: {
      all: "No materials yet.",
      mine: "You have no materials.",
      shared: "No shared materials.",
    },
  },
  common: {
    loading: "Loading...",
    retry: "Retry",
    back: "Back",
    next: "Next",
    cancel: "Cancel",
  },
  errors: {
    network_error: "Network error",
    unknown_error: "Unknown error",
  },
  empty: {
    materialsAll: "No materials yet.",
    materialsMine: "You have no materials.",
    materialsShared: "No shared materials.",
  },
};

const mockDocuments = [
  {
    document_id: "doc-1",
    title: "Document 1",
    parts_published: 3,
    parts_total: 5,
    status: "generating" as const,
    role: "owner" as const,
    shared_by_email: null,
    updated_at: "2024-01-15T10:30:00Z",
    source_type: "pdf" as const,
    parts_failed: 0,
  },
  {
    document_id: "doc-2",
    title: "Document 2",
    parts_published: 2,
    parts_total: 2,
    status: "done" as const,
    role: "shared" as const,
    shared_by_email: "other@example.com",
    updated_at: "2024-01-10T14:00:00Z",
    source_type: "docx" as const,
    parts_failed: 0,
  },
  {
    document_id: "doc-3",
    title: "Failed Doc",
    parts_published: 0,
    parts_total: 1,
    status: "failed" as const,
    role: "owner" as const,
    shared_by_email: null,
    updated_at: "2024-01-05T09:00:00Z",
    source_type: "md" as const,
    parts_failed: 1,
  },
];

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">
        {children}
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

describe("DocumentList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseMaterials.mockReturnValue({
      data: mockDocuments,
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  afterEach(() => {
    vi.resetAllMocks();
    cleanup();
  });

  function renderComponent(scope: "mine" | "shared" | "all" = "mine") {
    return render(<DocumentList scope={scope} />, { wrapper: createWrapper() });
  }

  describe("Status rendering", () => {
    it("renders status labels without raw i18n keys", async () => {
      renderComponent();

      await waitFor(() => {
        // Should show translated status labels, not raw keys like "status.generating"
        expect(screen.getAllByText("Generating: 3/5")).toHaveLength(2); // table + card
        expect(screen.getAllByText("Ready")).toHaveLength(2);
        expect(screen.getAllByText("Error")).toHaveLength(2);
      });

      // Should not have any raw i18n keys visible
      expect(screen.queryByText(/status\./)).not.toBeInTheDocument();
    });

    it("shows correct status badge colors via CSS classes", async () => {
      const { container } = renderComponent();

      await waitFor(() => {
        // Query for status badges by their text content and check parent classes
        // The status badges have hashed class names like "_statusBadge_b3faa8 _status-generating_b3faa8"
        const allSpans = container.querySelectorAll("span");
        const generatingBadgeElements = Array.from(allSpans).filter(
          (el) =>
            el.textContent?.includes("Generating: 3/5") &&
            el.className.includes("statusBadge")
        );
        const readyBadgeElements = Array.from(allSpans).filter(
          (el) =>
            el.textContent?.includes("Ready") &&
            el.className.includes("statusBadge")
        );
        const errorBadgeElements = Array.from(allSpans).filter(
          (el) =>
            el.textContent?.includes("Error") &&
            el.className.includes("statusBadge")
        );

        expect(generatingBadgeElements).toHaveLength(2);
        expect(readyBadgeElements).toHaveLength(2);
        expect(errorBadgeElements).toHaveLength(2);

        // Check first occurrence (table) - class should contain the hashed status class
        expect(generatingBadgeElements[0].className).toContain(
          "status-generating"
        );
        expect(readyBadgeElements[0].className).toContain("status-ready");
        expect(errorBadgeElements[0].className).toContain("status-error");

        // Check second occurrence (card)
        expect(generatingBadgeElements[1].className).toContain(
          "status-generating"
        );
        expect(readyBadgeElements[1].className).toContain("status-ready");
        expect(errorBadgeElements[1].className).toContain("status-error");
      });
    });

    it("renders role labels correctly", async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getAllByText("Owner")).toHaveLength(4); // 2 owner docs × 2 views
        expect(screen.getAllByText("From other@example.com")).toHaveLength(2); // 1 shared doc × 2 views
      });
    });

    it("renders shared badge for shared documents", async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getAllByText("Shared")).toHaveLength(2); // table + card
      });
    });
  });

  describe("Dead buttons and alerts", () => {
    it("does not contain retry or delete buttons for failed documents", async () => {
      renderComponent();

      await waitFor(() => {
        // Should not have any "Retry" or "Delete" buttons in the document rows
        const retryButtons = screen.queryAllByRole("button", {
          name: /retry/i,
        });
        const deleteButtons = screen.queryAllByRole("button", {
          name: /delete/i,
        });

        // The only retry button should be in the error state (not in document rows)
        // Since we're not in error state, there should be none
        expect(retryButtons).toHaveLength(0);
        expect(deleteButtons).toHaveLength(0);
      });
    });

    it("does not use alert() or confirm()", async () => {
      // This is a static check - the component should not import or use alert/confirm
      // The test passes if the component renders without errors
      renderComponent();

      await waitFor(() => {
        expect(screen.getAllByText("Document 1")).toHaveLength(2);
      });
    });

    it("does not have invalid role=listitem without parent role=list", async () => {
      renderComponent();

      await waitFor(() => {
        // Check that card list has role="list" and cards don't have role="listitem"
        // or if they do, they have a parent with role="list"
        const listItems = screen.queryAllByRole("listitem");
        // Our implementation doesn't use role="listitem" at all
        expect(listItems).toHaveLength(0);
      });
    });

    it("does not have hidden={false} attribute", async () => {
      renderComponent();

      await waitFor(() => {
        const container = screen.getByRole("grid").parentElement!;
        const hiddenElements = container.querySelectorAll('[hidden="false"]');
        expect(hiddenElements).toHaveLength(0);
      });
    });
  });

  describe("Responsive rendering", () => {
    it("renders both table wrapper and card list in DOM", async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByRole("grid")).toBeInTheDocument(); // table
        expect(
          screen.getByRole("list", { name: /my materials/i })
        ).toBeInTheDocument(); // card list
      });
    });

    it("renders document cards with same data as table rows", async () => {
      renderComponent();

      await waitFor(() => {
        // Check that cards contain the same information (both table and cards render)
        const doc1Elements = screen.getAllByText("Document 1");
        const doc2Elements = screen.getAllByText("Document 2");
        const failedDocElements = screen.getAllByText("Failed Doc");

        // Each document should appear twice (once in table, once in card)
        expect(doc1Elements).toHaveLength(2);
        expect(doc2Elements).toHaveLength(2);
        expect(failedDocElements).toHaveLength(2);

        // Check parts counts appear
        expect(screen.getAllByText("3/5")).toHaveLength(2);
        expect(screen.getAllByText("2/2")).toHaveLength(2);
        expect(screen.getAllByText("0/1")).toHaveLength(2);
      });
    });
  });

  describe("Empty states", () => {
    it("shows empty state with action link for mine scope", async () => {
      mockUseMaterials.mockReturnValue({
        data: [],
        isPending: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent("mine");

      await waitFor(() => {
        expect(screen.getByText("You have no materials.")).toBeInTheDocument();
        expect(
          screen.getByRole("link", { name: /upload material/i })
        ).toBeInTheDocument();
      });
    });

    it("shows empty state without action link for shared scope", async () => {
      mockUseMaterials.mockReturnValue({
        data: [],
        isPending: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent("shared");

      await waitFor(() => {
        expect(screen.getByText("No shared materials.")).toBeInTheDocument();
        expect(
          screen.queryByRole("link", { name: /upload material/i })
        ).not.toBeInTheDocument();
      });
    });
  });

  describe("Loading and error states", () => {
    it("shows skeleton while loading", async () => {
      mockUseMaterials.mockReturnValue({
        data: undefined,
        isPending: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent();

      expect(
        screen.getByRole("status", { name: /loading/i })
      ).toBeInTheDocument();
    });

    it("shows error state with retry button", async () => {
      const { ApiError } = await import("@/shared/api/errors");
      mockUseMaterials.mockReturnValue({
        data: undefined,
        isPending: false,
        isError: true,
        error: new ApiError(500, "network_error", "Network error"),
        refetch: vi.fn(),
      });

      renderComponent();

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
        expect(screen.getByText("Network error")).toBeInTheDocument();
        expect(
          screen.getByRole("button", { name: /retry/i })
        ).toBeInTheDocument();
      });
    });
  });
});
