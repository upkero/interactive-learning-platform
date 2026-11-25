import { getTranslations } from "next-intl/server";
import { PageShell } from "@/shared/ui";

export default async function QuizPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  const t = await getTranslations({ locale, namespace: "quiz" });

  return (
    <PageShell title={t("title")}>
      <div className="stub">
        <h1>{t("title")}</h1>
        <p>Квиз для части {id} (Э7) — заглушка.</p>
      </div>
    </PageShell>
  );
}
