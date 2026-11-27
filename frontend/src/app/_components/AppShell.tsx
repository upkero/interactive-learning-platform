import { Link } from "@/shared/i18n/navigation";
import { getTranslations } from "next-intl/server";
import { NavLinks } from "./NavLinks";
import { LocaleSwitch } from "@/features/locale";
import { UserMenu } from "@/features/auth";
import { QuotaCard } from "@/features/materials";
import styles from "./AppShell.module.css";

interface AppShellProps {
  children: React.ReactNode;
  locale: string;
}

export async function AppShell({ children, locale }: AppShellProps) {
  const tCommon = await getTranslations({ locale, namespace: "common" });
  const tMaterials = await getTranslations({ locale, namespace: "materials" });
  const tUpload = await getTranslations({ locale, namespace: "upload" });

  return (
    <div className={styles.shell}>
      {/* Icon Rail - Left side */}
      <aside className={styles.iconRail} aria-label={tCommon("navigation")}>
        <div className={styles.railTop}>
          <Link
            href="/materials"
            className={styles.brand}
            aria-label={tCommon("appName")}
          >
            <span className={styles.brandMark} aria-hidden="true">
              <svg
                width="28"
                height="28"
                viewBox="0 0 32 32"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <rect width="32" height="32" rx="6" fill="currentColor" />
                <path
                  d="M8 16L14 22L24 10"
                  stroke="white"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <span className={styles.brandText}>{tCommon("appName")}</span>
          </Link>
        </div>

        <NavLinks />

        <div className={styles.railBottom}>
          <LocaleSwitch />
          <UserMenu />
        </div>
      </aside>

      {/* Main Content Area - Right side */}
      <main className={styles.main}>
        {/* Top bar with quota card */}
        <div className={styles.topBar}>
          <QuotaCard />
        </div>

        {/* Content container */}
        <div className={styles.content}>{children}</div>
      </main>

      {/* Mobile bottom navigation */}
      <nav
        className={styles.mobileNav}
        aria-label={tCommon("mobileNavigation")}
      >
        <Link
          href="/materials"
          className={styles.mobileNavItem}
          aria-current="page"
        >
          <span className={styles.mobileNavIcon} aria-hidden="true">
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </span>
          <span className={styles.mobileNavLabel}>{tMaterials("title")}</span>
        </Link>
        <Link href="/upload" className={styles.mobileNavItem}>
          <span className={styles.mobileNavIcon} aria-hidden="true">
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </span>
          <span className={styles.mobileNavLabel}>{tUpload("title")}</span>
        </Link>
      </nav>
    </div>
  );
}
