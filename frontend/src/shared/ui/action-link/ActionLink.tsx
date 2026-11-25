import { Link } from "@/shared/i18n/navigation";
import type { ReactNode, AnchorHTMLAttributes } from "react";
import styles from "./ActionLink.module.css";

export interface ActionLinkProps extends Omit<
  AnchorHTMLAttributes<HTMLAnchorElement>,
  "href" | "children"
> {
  href: string;
  variant?: "primary" | "secondary";
  children: ReactNode;
  disabled?: boolean;
}

export function ActionLink({
  href,
  variant = "primary",
  children,
  disabled,
  className,
  ...rest
}: ActionLinkProps) {
  if (disabled) {
    return (
      <span
        className={`${styles.link} ${styles[variant]} ${styles.disabled} ${className || ""}`}
        {...rest}
        aria-disabled="true"
      >
        {children}
      </span>
    );
  }
  return (
    <Link
      href={href}
      className={`${styles.link} ${styles[variant]} ${className || ""}`}
      {...rest}
    >
      {children}
    </Link>
  );
}
