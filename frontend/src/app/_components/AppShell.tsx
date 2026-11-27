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
                  stroke="var(--g-color-bg-dark)"
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
      <div className={styles.mobileNav}>
        <NavLinks mobile />
      </div>
    </div>
  );
}
