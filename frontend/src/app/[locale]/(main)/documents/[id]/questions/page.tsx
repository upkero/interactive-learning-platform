import { QuestionsFeature } from "@/features/questions";

export default async function QuestionsPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = await params;

  return <QuestionsFeature documentId={id} />;
}
