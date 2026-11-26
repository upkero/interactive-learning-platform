import { getTranslations } from "next-intl/server";
import { PageShell } from "@/shared/ui";

export default async function QuestionsPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  const t = await getTranslations({ locale, namespace: "questions" });

  return (
    <PageShell title={t("title")}>
      <div className="stub">
        <h1>{t("title")}</h1>
        <p>Параметры генерации для документа {id} (Э4) — заглушка.</p>
      </div>
    </PageShell>
  );
}
