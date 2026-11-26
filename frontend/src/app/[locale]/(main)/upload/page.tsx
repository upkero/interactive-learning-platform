import { Suspense } from "react";
import { getTranslations } from "next-intl/server";
import { PageShell, ActionLink } from "@/shared/ui";
import { UploadFeature } from "@/features/upload";

export default async function UploadPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "upload" });
  const tCommon = await getTranslations({ locale, namespace: "common" });

  return (
    <PageShell
      title={t("title")}
      actions={
        <ActionLink href={`/${locale}/materials`} variant="secondary">
          {tCommon("back")}
        </ActionLink>
      }
    >
      <Suspense
        fallback={
          <div className="loading" aria-live="polite">
            {tCommon("loading")}
          </div>
        }
      >
        <UploadFeature />
      </Suspense>
    </PageShell>
  );
}
