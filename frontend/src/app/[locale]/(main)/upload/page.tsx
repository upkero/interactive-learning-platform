import { getTranslations } from "next-intl/server";
import { PageShell } from "@/shared/ui";

export default async function UploadPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "upload" });

  return (
    <PageShell title={t("title")}>
      <div className="stub">
        <h1>{t("title")}</h1>
        <p>Страница загрузки материала (Э2) — заглушка.</p>
      </div>
    </PageShell>
  );
}
