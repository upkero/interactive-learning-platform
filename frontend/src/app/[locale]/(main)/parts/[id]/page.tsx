import { PartPageClient } from "./PartPageClient";

export default async function PartPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = await params;
  return <PartPageClient partId={id} />;
}
