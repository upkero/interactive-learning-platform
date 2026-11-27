"use client";

import { Link } from "@/shared/i18n/navigation";
import { usePathname } from "@/shared/i18n/navigation-client";
import { useTranslations } from "next-intl";
import { UserMenu } from "@/features/auth";
import styles from "./NavLinks.module.css";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

export function NavLinks({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname();
  const tCommon = useTranslations("common");
  const tMaterials = useTranslations("materials");
  const tUpload = useTranslations("upload");

  const navItems: NavItem[] = [
    {
      href: "/materials",
      label: tMaterials("title"),
      icon: (
        <svg
          width="20"
          height="20"
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
      ),
    },
    {
      href: "/upload",
      label: tUpload("title"),
      icon: (
        <svg
          width="20"
          height="20"
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
      ),
    },
  ];

  return (
    <nav
      className={mobile ? styles.mobile : undefined}
      aria-label={tCommon(mobile ? "mobileNavigation" : "mainNavigation")}
    >
      <ul className={styles.navList}>
        {navItems.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={`${styles.navLink} ${pathname === item.href ? styles.active : ""}`}
              aria-current={pathname === item.href ? "page" : undefined}
            >
              <span className={styles.navIcon} aria-hidden="true">
                {item.icon}
              </span>
              <span className={styles.navLabel}>{item.label}</span>
            </Link>
          </li>
        ))}
        {mobile && (
          <li>
            <UserMenu variant="mobile" />
          </li>
        )}
      </ul>
    </nav>
  );
}
