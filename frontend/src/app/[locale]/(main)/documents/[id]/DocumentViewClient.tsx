'use client';

import { useCallback, useState } from 'react';
import { DocumentViewFeature } from '@/features/document-view';
import { ShareModal } from '@/features/share';

interface DocumentViewClientProps {
  documentId: string;
  initialPartId?: string;
}

export function DocumentViewClient({ documentId, initialPartId }: DocumentViewClientProps) {
  const [shareOpen, setShareOpen] = useState(false);
  const closeShare = useCallback(() => { setShareOpen(false); }, []);

  return (
    <>
      <DocumentViewFeature
        documentId={documentId}
        initialPartId={initialPartId}
        onShare={() => { setShareOpen(true); }}
      />
      {shareOpen && <ShareModal documentId={documentId} onClose={closeShare} />}
    </>
  );
}
