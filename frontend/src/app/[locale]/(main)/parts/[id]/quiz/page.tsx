import { QuizFeature } from '@/features/quiz';

export default async function QuizPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = await params;

  return <QuizFeature partId={id} key={id} />;
}
