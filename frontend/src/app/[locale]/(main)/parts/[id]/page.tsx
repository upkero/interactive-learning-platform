import { getTranslations } from "next-intl/server";
import { PageShell } from "@/shared/ui";

export default async function PartPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  const t = await getTranslations({ locale, namespace: "viewer" });

  return (
    <PageShell title={t("materialTitle")}>
      <div className="stub">
        <h1>{t("materialTitle")}</h1>
        <p>Материал (часть {id}) (Э6) — заглушка.</p>
      </div>
    </PageShell>
  );
}
