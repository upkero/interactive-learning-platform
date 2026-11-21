import { DocumentViewClient } from './DocumentViewClient';

export default async function DocumentPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = await params;
  return <DocumentViewClient documentId={id} />;
}