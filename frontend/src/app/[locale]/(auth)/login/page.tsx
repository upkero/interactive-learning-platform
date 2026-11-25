import { getTranslations } from "next-intl/server";
import { Suspense } from "react";
import { LoginPageClient } from "./LoginPageClient";
import styles from "../auth.module.css";

export default async function LoginPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "common" });

  return (
    <div className={styles.content}>
      <Suspense fallback={<p className={styles.loading}>{t("loading")}</p>}>
        <LoginPageClient />
      </Suspense>
    </div>
  );
}
