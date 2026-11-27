import { PartViewClient } from "./PartViewClient";

export default async function PartPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { id } = await params;
  return <PartViewClient key={id} partId={id} />;
}
