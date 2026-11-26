import { TopicsFeature } from "@/features/topics";

export default async function TopicsPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = await params;

  return <TopicsFeature documentId={id} />;
}
