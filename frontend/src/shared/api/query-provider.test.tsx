import { useQueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import { QueryProvider } from "./query-provider";

const { usePathname, replace, post } = vi.hoisted(() => ({
  usePathname: vi.fn<() => string>(),
  replace: vi.fn(),
  post: vi.fn(),
}));

vi.mock("next-intl", () => ({ useLocale: () => "en" }));
vi.mock("@/shared/i18n/navigation-client", () => ({
  useNextPathname: usePathname,
  useNextRouter: () => ({ replace }),
}));
vi.mock("./client", () => ({ apiClient: { POST: post } }));

const unauthorized = new ApiError(401);
const fetchCurrentUser = () => Promise.reject(unauthorized);

describe("QueryProvider", () => {
  beforeEach(() => vi.clearAllMocks());

  it.each(["/en/login", "/en/register"])(
    "lets %s handle an unauthenticated session probe",
    async (pathname) => {
      usePathname.mockReturnValue(pathname);
      const { result } = renderHook(useQueryClient, { wrapper: QueryProvider });

      await expect(
        result.current.fetchQuery({
          queryKey: ["me"],
          queryFn: fetchCurrentUser,
        })
      ).rejects.toBe(unauthorized);

      expect(post).not.toHaveBeenCalled();
      expect(replace).not.toHaveBeenCalled();
    }
  );

  it("redirects to login with the current protected path after navigation", async () => {
    usePathname.mockReturnValue("/en/login");
    const { result, rerender } = renderHook(useQueryClient, {
      wrapper: QueryProvider,
    });

    usePathname.mockReturnValue("/en/documents/42");
    rerender();
    await expect(
      result.current.fetchQuery({ queryKey: ["me"], queryFn: fetchCurrentUser })
    ).rejects.toBe(unauthorized);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/en/login?next=%2Fen%2Fdocuments%2F42")
    );
    expect(post).toHaveBeenCalledWith("/api/v1/auth/logout");
  });
});
