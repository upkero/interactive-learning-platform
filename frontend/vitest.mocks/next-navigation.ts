import { vi } from "vitest";

export const useRouter = vi.fn(() => ({
  replace: vi.fn(),
  push: vi.fn(),
  back: vi.fn(),
  prefetch: vi.fn(),
}));
export const usePathname = vi.fn(() => "/");
export const useSearchParams = vi.fn(() => new URLSearchParams());
export const useParams = vi.fn(() => ({}));
export const redirect = vi.fn();
export const permanentRedirect = vi.fn();
