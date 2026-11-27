import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { AppShell } from "./AppShell";
import { SessionGate } from "@/features/auth";
import en from "@/shared/i18n/messages/en.json";

const { get, post, replace } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next-intl/server", async () => {
  const { createTranslator } = await import("next-intl");
  const { default: messages } = await import("@/shared/i18n/messages/en.json");
  return {
    getTranslations: ({
      namespace,
    }: {
      namespace: "common" | "materials" | "upload";
    }) => createTranslator({ locale: "en", messages, namespace }),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/en/materials",
  useSearchParams: () => new URLSearchParams(),
  redirect: vi.fn(),
  permanentRedirect: vi.fn(),
}));

vi.mock("@/shared/i18n/navigation", () => ({
  Link: ({ children, ...props }: React.ComponentProps<"a">) => (
    <a {...props}>{children}</a>
  ),
}));

vi.mock("@/shared/api/client", () => ({
  apiClient: { GET: get, POST: post },
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it.each([
  ["complementary", en.common.navigation],
  ["navigation", en.common.mobileNavigation],
])("logs out from the authorized %s UI", async (role, name) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  get.mockImplementation(async (path: string) => ({
    response: new Response(),
    data:
      path === "/api/v1/me"
        ? { email: "student@example.test" }
        : { available: 10, monthly_limit: 20, period_end: "2026-12-01" },
  }));
  post.mockResolvedValue({ response: new Response(), data: { status: "ok" } });

  const shell = await AppShell({ locale: "en", children: <h1>Materials</h1> });
  render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en} timeZone="UTC">
        <SessionGate>{shell}</SessionGate>
      </NextIntlClientProvider>
    </QueryClientProvider>
  );

  const region = await screen.findByRole(role, { name });
  const logout = within(region).getByRole("button", { name: en.common.logout });
  expect(logout).toBeEnabled();
  fireEvent.click(logout);

  await waitFor(() => expect(replace).toHaveBeenCalledWith("/en/login"));
  expect(post).toHaveBeenCalledExactlyOnceWith("/api/v1/auth/logout");
});
