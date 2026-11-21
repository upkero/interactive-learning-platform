import { ProgressFeature } from '@/features/progress';

export default async function ProgressPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = await params;

  return <ProgressFeature documentId={id} />;
}