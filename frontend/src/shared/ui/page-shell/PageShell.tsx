import type { ReactNode } from "react";
import styles from "./PageShell.module.css";

export interface PageShellProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  children?: ReactNode;
}

export function PageShell({
  title,
  description,
  actions,
  children,
}: PageShellProps) {
  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <h1 className={styles.title}>{title}</h1>
          {description ? (
            <p className={styles.description}>{description}</p>
          ) : null}
        </div>
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </header>
      {children ? <div className={styles.body}>{children}</div> : null}
    </section>
  );
}
