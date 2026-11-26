import { getTranslations } from "next-intl/server";
import { PageShell } from "@/shared/ui";

export default async function ProgressPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  const t = await getTranslations({ locale, namespace: "progress" });

  return (
    <PageShell title={t("title")}>
      <div className="stub">
        <h1>{t("title")}</h1>
        <p>Прогресс генерации для документа {id} (Э5) — заглушка.</p>
      </div>
    </PageShell>
  );
}
