'use client';

import { useState } from 'react';
import { DocumentViewFeature } from '@/features/document-view';
import { ShareModal } from '@/features/share';

interface DocumentViewClientProps {
  documentId: string;
  initialPartId?: string;
}

export function DocumentViewClient({ documentId, initialPartId }: DocumentViewClientProps) {
  const [shareOpen, setShareOpen] = useState(false);

  return (
    <>
      <DocumentViewFeature
        documentId={documentId}
        initialPartId={initialPartId}
        onShare={() => { setShareOpen(true); }}
      />
      <ShareModal
        documentId={documentId}
        isOpen={shareOpen}
        onClose={() => { setShareOpen(false); }}
      />
    </>
  );
}
