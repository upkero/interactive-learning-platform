import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";
import type { DocumentOut } from "@/entities/document";
import messages from "@/shared/i18n/messages/en.json";
import { ParsingCard } from "../ParsingCard";

const { getDocument, replace } = vi.hoisted(() => ({
  getDocument: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("@/shared/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/api")>()),
  apiClient: { GET: getDocument },
}));

vi.mock("@/shared/i18n/navigation-client", () => ({
  useRouter: () => ({ replace }),
}));

const document: DocumentOut = {
  id: "doc-1",
  title: "Test document",
  status: "uploaded",
  error_code: null,
  page_count: null,
  role: "owner",
  source_url: null,
  parts: [],
  shared_with: [],
};

function documentResponse(data: DocumentOut) {
  return { data, response: new Response(null, { status: 200 }) };
}

function renderCard() {
  replace.mockClear();
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <NextIntlClientProvider locale="en" messages={messages}>
        <ParsingCard documentId={document.id} />
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

describe("ParsingCard", () => {
  it("opens topics when polling finds a parsed document", async () => {
    getDocument
      .mockResolvedValueOnce(documentResponse(document))
      .mockResolvedValue(documentResponse({ ...document, status: "parsed" }));

    renderCard();

    expect(await screen.findByRole("progressbar")).toBeInTheDocument();
    await waitFor(
      () => expect(replace).toHaveBeenCalledWith("/documents/doc-1/topics"),
      { timeout: 4000 }
    );
  }, 5000);

  it("shows a persisted parsing error and lets the user pick another file", async () => {
    getDocument.mockResolvedValue(
      documentResponse({
        ...document,
        status: "failed",
        error_code: "empty_document",
      })
    );

    renderCard();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      messages.upload.documentErrors.empty_document
    );
    expect(
      screen.getByRole("button", { name: messages.upload.replaceFileButton })
    ).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
