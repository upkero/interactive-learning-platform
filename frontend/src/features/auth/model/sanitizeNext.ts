export function sanitizeNextUrl(
  nextParam: string | null | undefined,
  defaultPath = "/materials"
): string {
  if (!nextParam) return defaultPath;
  const trimmed = nextParam.trim();

  if (
    !trimmed.startsWith("/") ||
    trimmed.startsWith("//") ||
    trimmed.includes("://") ||
    trimmed.includes("\\")
  ) {
    return defaultPath;
  }

  return trimmed;
}
