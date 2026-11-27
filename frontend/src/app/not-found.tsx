import { getLocale, getTranslations } from "next-intl/server";

export default async function NotFound() {
  const locale = await getLocale();
  const t = await getTranslations("common");

  return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <h1 style={{ fontSize: "2rem", marginBottom: "1rem" }}>
        {t("notFound")}
      </h1>
      <p style={{ marginBottom: "2rem" }}>{t("notFoundDescription")}</p>
      <a
        href={`/${locale}/materials`}
        style={{
          display: "inline-block",
          padding: "0.5rem 1rem",
          backgroundColor: "#0066cc",
          color: "white",
          borderRadius: "4px",
          textDecoration: "none",
        }}
      >
        {t("goToMaterials")}
      </a>
    </div>
  );
}
