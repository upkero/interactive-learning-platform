"use client";

import { useSearchParams } from "@/shared/i18n/navigation-client";
import { UploadDropzone } from "./UploadDropzone";
import { ParsingCard } from "./ParsingCard";

export function UploadFeature() {
  const searchParams = useSearchParams();
  const docId = searchParams.get("document");

  if (docId) {
    return <ParsingCard documentId={docId} />;
  }

  return <UploadDropzone />;
}
