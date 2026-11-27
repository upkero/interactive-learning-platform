import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, expect, it, vi } from "vitest";
import type { DocumentOut } from "@/entities/document";
import { apiClient } from "@/shared/api";
import messages from "@/shared/i18n/messages/en.json";
import { ProgressFeature } from "./ProgressFeature";

const router = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("@/shared/i18n/navigation-client", () => ({ useRouter: () => router }));

class ProgressEventSource extends EventTarget {
  static sources: ProgressEventSource[] = [];
  close = vi.fn();

  constructor(readonly url: string) {
    super();
    ProgressEventSource.sources.push(this);
  }

  emit(type: string, payload: object, lastEventId: string) {
    this.dispatchEvent(
      new MessageEvent(type, {
        data: JSON.stringify({
          type,
          message: "Progress update",
          ts: "2026-11-27T10:00:00Z",
          ...payload,
        }),
        lastEventId,
      })
    );
  }
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("renders the fetched part and refreshes it from progress events before redirecting", async () => {
  const documentId = "65f32703-3d6b-4d25-8fc4-642d5a416ddc";
  const partId = "a092065b-154a-4115-882b-869c989d9beb";
  const part = { id: partId, index: 0, title: "Introduction" };
  let document: DocumentOut = {
    id: documentId,
    title: "Study guide",
    page_count: 1,
    role: "owner",
    source_url: null,
    status: "generating",
    parts: [{ ...part, status: "queued" }],
  };
  const get = vi.spyOn(apiClient, "GET").mockImplementation(async () => ({
    data: document,
    response: new Response(),
  }));
  vi.stubGlobal("EventSource", ProgressEventSource);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">
      <QueryClientProvider client={queryClient}>
        <ProgressFeature documentId={documentId} />
      </QueryClientProvider>
    </NextIntlClientProvider>
  );

  await screen.findByRole("heading", { name: part.title });
  expect(screen.getByText(messages.progress.partStatus.queued)).toBeVisible();
  expect(get).toHaveBeenCalledWith("/api/v1/documents/{document_id}", {
    params: { path: { document_id: documentId } },
  });
  const [source] = ProgressEventSource.sources;
  expect(new URL(source.url).pathname).toBe(
    `/api/v1/documents/${documentId}/events`
  );

  document = { ...document, parts: [{ ...part, status: "main_pass" }] };
  act(() => {
    source.emit("part_status", { part_id: partId, stage: "main_pass" }, "1-0");
  });
  await screen.findByRole("progressbar", {
    name: messages.progress.partStatus.mainPass,
  });

  document = { ...document, parts: [{ ...part, status: "published" }] };
  act(() => {
    source.emit("part_ready", { part_id: partId }, "2-0");
  });
  const publishedLinks = await screen.findAllByRole("link", {
    name: messages.progress.openMaterialButton,
  });
  expect(publishedLinks).toHaveLength(1);
  expect(publishedLinks[0]).toHaveAttribute("href", `/en/parts/${partId}`);
  expect(screen.getAllByRole("listitem")).toHaveLength(1);
  expect(router.replace).not.toHaveBeenCalled();

  document = { ...document, status: "done" };
  act(() => {
    source.emit("document_done", { stage: "done" }, "3-0");
  });
  await waitFor(() =>
    expect(router.replace).toHaveBeenCalledWith(`/parts/${partId}`)
  );
  expect(source.close).toHaveBeenCalled();
});
