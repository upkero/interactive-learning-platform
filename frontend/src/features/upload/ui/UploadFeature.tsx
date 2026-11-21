'use client';

import { useSearchParams } from 'next/navigation';
import { UploadDropzone } from './UploadDropzone';
import { ParsingCard } from './ParsingCard';

export function UploadFeature() {
  const searchParams = useSearchParams();
  const docId = searchParams.get('doc');

  if (docId) {
    return <ParsingCard documentId={docId} />;
  }

  return <UploadDropzone />;
}