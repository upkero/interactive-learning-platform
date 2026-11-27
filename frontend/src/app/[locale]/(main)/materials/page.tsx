import { getTranslations } from "next-intl/server";
import { ActionLink, PageShell } from "@/shared/ui";
import { MaterialsPageContent } from "./MaterialsPageContent";

export default async function MaterialsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "materials" });

  return (
    <PageShell
      title={t("title")}
      actions={
        <ActionLink href={`/${locale}/upload`}>{t("uploadButton")}</ActionLink>
      }
    >
      <MaterialsPageContent />
    </PageShell>
  );
}
