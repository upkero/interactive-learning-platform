"use client";

import { useTranslations } from "next-intl";
import { isApiError } from "./errors";

export function useApiErrorMessage(error: unknown): string {
  const tErrors = useTranslations("errors");

  if (isApiError(error)) {
    return tErrors(error.code);
  }

  if (error instanceof TypeError && error.message.includes("fetch")) {
    return tErrors("network_error");
  }

  if (error instanceof Error) {
    return tErrors("unknown_error");
  }

  return tErrors("unknown_error");
}
