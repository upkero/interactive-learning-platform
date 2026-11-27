import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import en from "@/shared/i18n/messages/en.json";
import ru from "@/shared/i18n/messages/ru.json";
import { MaterialsPageContent } from "./MaterialsPageContent";

const { route, get, post } = vi.hoisted(() => ({
  route: { filter: "", push: vi.fn() },
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@/shared/i18n/navigation", () => ({
  Link: ({ href, children, ...props }: React.ComponentProps<"a">) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/shared/i18n/navigation-client", () => ({
  useRouter: () => ({ push: route.push }),
  useSearchParams: () => new URLSearchParams(route.filter),
}));

vi.mock("@/shared/api/client", () => ({
  apiClient: { GET: get, POST: post },
}));

const material = {
  document_id: "owned-document",
  role: "owner",
  title: "Biology",
  status: "done",
  parts_published: 1,
  parts_total: 1,
  updated_at: "2026-01-01T00:00:00Z",
};
const recipient = "student@example.test";
const success = (data: unknown) => ({ data, response: new Response() });

function renderMaterials(locale: "ru" | "en" = "ru") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider
        locale={locale}
        messages={locale === "ru" ? ru : en}
        timeZone="UTC"
      >
        <MaterialsPageContent />
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  route.filter = "";
  let sharedWith: { email: string; display_name: string }[] = [];
  get.mockImplementation(
    async (
      path: string,
      options?: { params: { query: { filter: string } } }
    ) => {
      switch (path) {
        case "/api/v1/me/materials":
          if (options?.params.query.filter === "shared") {
            return success([
              {
                ...material,
                document_id: "shared-document",
                title: "Chemistry",
                role: "shared",
              },
            ]);
          }
          return success([material]);
        case "/api/v1/me/quota":
          return success({
            available: 5,
            monthly_limit: 10,
            period_end: "2026-12-01",
          });
        case "/api/v1/documents/{document_id}":
          return success({ role: "owner", shared_with: sharedWith });
        default:
          throw new Error(`Unexpected GET ${path}`);
      }
    }
  );
  post.mockImplementation(async () => {
    sharedWith = [{ email: recipient, display_name: "Student" }];
    return success({ status: "ok" });
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("sharing from the materials page", () => {
  it.each([
    ["ru", "Поделиться", "Поделиться материалом"],
    ["en", "Share", "Share material"],
  ] as const)(
    "opens the owner dialog in %s without navigation",
    async (locale, action, title) => {
      renderMaterials(locale);
      const button = await screen.findByRole("button", {
        name: `${action}: Biology`,
      });
      button.focus();
      fireEvent.click(button);

      expect(
        await screen.findByRole("dialog", { name: title })
      ).toBeInTheDocument();
      expect(route.push).not.toHaveBeenCalled();

      fireEvent.keyDown(document, { key: "Escape" });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(button).toHaveFocus();
    }
  );

  it("grants access to the selected document and refreshes its recipients", async () => {
    renderMaterials();
    fireEvent.click(
      await screen.findByRole("button", { name: "Поделиться: Biology" })
    );
    const dialog = within(await screen.findByRole("dialog"));
    fireEvent.change(
      await dialog.findByRole("textbox", { name: ru.share.emailLabel }),
      {
        target: { value: recipient },
      }
    );
    fireEvent.click(dialog.getByRole("button", { name: ru.share.grantButton }));

    expect(await dialog.findByText(recipient)).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith("/api/v1/materials/share", {
      body: { document_id: material.document_id, email: recipient },
    });
  });

  it("displays the localized API error if the recipient is unregistered", async () => {
    post.mockResolvedValueOnce({
      response: Response.json(
        { error_code: "recipient_not_registered" },
        { status: 422 }
      ),
    });

    renderMaterials();
    fireEvent.click(
      await screen.findByRole("button", { name: "Поделиться: Biology" })
    );
    const dialog = within(await screen.findByRole("dialog"));
    fireEvent.change(
      await dialog.findByRole("textbox", { name: ru.share.emailLabel }),
      {
        target: { value: recipient },
      }
    );
    fireEvent.click(dialog.getByRole("button", { name: ru.share.grantButton }));

    expect(await dialog.findByRole("alert")).toHaveTextContent(
      ru.share.userNotFound
    );
  });

  it("does not offer sharing for a received document", async () => {
    route.filter = "filter=shared";
    renderMaterials("en");

    expect(
      await screen.findByRole("link", { name: /^Chemistry/ })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Share: Chemistry" })
    ).not.toBeInTheDocument();
  });
});
