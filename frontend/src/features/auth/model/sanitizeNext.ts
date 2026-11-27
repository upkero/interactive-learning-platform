import { locales } from "@/shared/i18n/config";

const returnUrlOrigin = "https://grasp.invalid";

export function sanitizeNextUrl(
  nextParam: string | null | undefined,
  locale: string
): string {
  const fallback = `/${locale}/materials`;
  const trimmed = nextParam?.trim();

  if (
    !trimmed?.startsWith("/") ||
    trimmed.startsWith("//") ||
    trimmed.includes("://") ||
    trimmed.includes("\\")
  ) {
    return fallback;
  }

  try {
    const target = new URL(trimmed, returnUrlOrigin);
    if (target.origin !== returnUrlOrigin || target.pathname.startsWith("//")) {
      return fallback;
    }
    const [, prefix] = target.pathname.split("/");
    const path = target.pathname + target.search + target.hash;
    return locales.some((candidate) => candidate === prefix)
      ? path
      : `/${locale}${path}`;
  } catch {
    return fallback;
  }
}
