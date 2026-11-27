"use client";

import { useTranslations } from "next-intl";
import { useLogout } from "../api";
import styles from "./UserMenu.module.css";

interface UserMenuProps {
  variant?: "rail" | "mobile";
}

export function UserMenu({ variant = "rail" }: UserMenuProps) {
  const t = useTranslations("common");
  const logoutMutation = useLogout();

  return (
    <div className={variant === "mobile" ? styles.mobileMenu : styles.menu}>
      <button
        type="button"
        onClick={() => {
          logoutMutation.mutate();
        }}
        disabled={logoutMutation.isPending}
        className={styles.button}
        aria-label={t("logout")}
      >
        <span className={styles.icon} aria-hidden="true">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </span>
        <span className={styles.label}>{t("logout")}</span>
      </button>
    </div>
  );
}
