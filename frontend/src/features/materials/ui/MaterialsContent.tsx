"use client";

import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "@/shared/i18n/navigation-client";
import { DocumentList } from "./DocumentList";
import { QuotaCard } from "./QuotaCard";
import styles from "./MaterialsContent.module.css";

type Filter = "all" | "mine" | "shared";

const FILTERS: { value: Filter; labelKey: string }[] = [
  { value: "all", labelKey: "filterAll" },
  { value: "mine", labelKey: "filterMine" },
  { value: "shared", labelKey: "filterShared" },
];

interface MaterialsContentProps {
  onShare: (documentId: string) => void;
}

export function MaterialsContent({ onShare }: MaterialsContentProps) {
  const t = useTranslations("materials");
  const searchParams = useSearchParams();
  const router = useRouter();

  const filterValue = searchParams.get("filter");
  const currentFilter =
    filterValue === "mine" || filterValue === "shared" ? filterValue : "all";

  const handleFilterChange = (filter: Filter) => {
    const params = new URLSearchParams(searchParams.toString());
    if (filter === "all") {
      params.delete("filter");
    } else {
      params.set("filter", filter);
    }
    router.push(`?${params.toString()}`, { scroll: false });
  };

  return (
    <div className={styles.container}>
      {/* Quota Card */}
      <aside className={styles.quotaSidebar} aria-label={t("quotaTitle")}>
        <QuotaCard />
      </aside>

      {/* Main Content */}
      <main className={styles.main}>
        {/* Filter Tabs */}
        <nav
          className={styles.filterTabs}
          aria-label={t("filterAll")}
          role="tablist"
        >
          {FILTERS.map(({ value, labelKey }) => (
            <button
              key={value}
              role="tab"
              aria-selected={currentFilter === value}
              aria-controls={`panel-${value}`}
              id={`tab-${value}`}
              className={`${styles.filterTab} ${currentFilter === value ? styles.active : ""}`}
              onClick={() => {
                handleFilterChange(value);
              }}
            >
              {t(labelKey)}
            </button>
          ))}
        </nav>

        {/* Document List Panels */}
        <div className={styles.panels}>
          {FILTERS.map(({ value }) => (
            <div
              key={value}
              role="tabpanel"
              id={`panel-${value}`}
              aria-labelledby={`tab-${value}`}
              hidden={currentFilter !== value}
              className={styles.panel}
            >
              <DocumentList
                scope={value === "all" ? undefined : value}
                onShare={onShare}
              />
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
