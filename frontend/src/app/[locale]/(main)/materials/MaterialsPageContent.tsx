"use client";

import { useCallback, useState } from "react";
import { MaterialsContent } from "@/features/materials";
import { ShareModal } from "@/features/share";

export function MaterialsPageContent() {
  const [shareDocumentId, setShareDocumentId] = useState<string | null>(null);
  const closeShare = useCallback(() => {
    setShareDocumentId(null);
  }, []);

  return (
    <>
      <MaterialsContent onShare={setShareDocumentId} />
      {shareDocumentId && (
        <ShareModal
          key={shareDocumentId}
          documentId={shareDocumentId}
          onClose={closeShare}
        />
      )}
    </>
  );
}
