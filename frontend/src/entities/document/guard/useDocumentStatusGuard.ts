"use client";

import { useCallback, useEffect, useRef } from "react";
import { useRouter } from "@/shared/i18n/navigation-client";
import { useDocument } from "../model/useDocument";
import { isApiError } from "@/shared/api/errors";
import type { MaterialStatus } from "./types";
import {
  getRedirectForStatus,
  getRouteForStep,
  type WizardStep,
} from "./types";

interface UseDocumentStatusGuardOptions {
  documentId: string;
  /** The wizard step this screen corresponds to */
  currentStep: WizardStep;
  /** Callback when redirect is triggered (optional, for analytics etc.) */
  onRedirect?: (fromStep: WizardStep, toStep: WizardStep) => void;
  /** If true, redirect will use router.replace instead of router.push */
  useReplace?: boolean;
}

interface UseDocumentStatusGuardResult {
  /** Current material status (null while loading) */
  status: MaterialStatus | null;
  /** True while document is loading */
  isLoading: boolean;
  /** Error if document failed to load */
  error: Error | null;
  /** True if a redirect has been triggered */
  hasRedirected: boolean;
}

/**
 * Centralized document status guard for wizard screens.
 *
 * This hook:
 * - Fetches the document status
 * - Checks if the current wizard step is allowed for the document's status
 * - Automatically redirects to the correct step if not allowed
 * - Shows loading state while checking
 * - Prevents content flashing during redirect
 *
 * Usage:
 *   const { status, isLoading, hasRedirected } = useDocumentStatusGuard({
 *     documentId,
 *     currentStep: 'topics',
 *   });
 *
 *   if (isLoading) return <Skeleton />;
 *   if (hasRedirected) return null; // Redirect in progress
 *   // Render your feature
 */
export function useDocumentStatusGuard({
  documentId,
  currentStep,
  onRedirect,
  useReplace = true,
}: UseDocumentStatusGuardOptions): UseDocumentStatusGuardResult {
  const router = useRouter();

  const { data: document, isLoading, error } = useDocument(documentId);

  const status = document?.status ?? null;
  const hasRedirectedRef = useRef(false);

  // Check if redirect is needed and perform it
  useEffect(() => {
    if (isLoading || !document || hasRedirectedRef.current) return;

    const redirectStep = getRedirectForStatus(document.status, currentStep);

    if (redirectStep) {
      hasRedirectedRef.current = true;
      onRedirect?.(currentStep, redirectStep);

      const targetRoute = getRouteForStep(redirectStep, documentId);

      if (useReplace) {
        router.replace(targetRoute);
      } else {
        router.push(targetRoute);
      }
    }
  }, [
    document,
    isLoading,
    currentStep,
    documentId,
    router,
    onRedirect,
    useReplace,
  ]);

  // Handle error states (404, 403, etc.) using isApiError and error.code/error.status
  const isNotFound = isApiError(error) && error.code === "document_not_found";
  const isForbidden = isApiError(error) && error.status === 403;

  return {
    status,
    isLoading,
    error: isNotFound || isForbidden ? error : null,
    hasRedirected: hasRedirectedRef.current,
  };
}

/**
 * Hook for screens that need to handle document not found / access denied.
 * Returns a redirect function to materials page.
 */
export function useDocumentErrorRedirect() {
  const router = useRouter();

  const redirectToMaterials = useCallback(() => {
    router.push("/materials");
  }, [router]);

  return { redirectToMaterials };
}
