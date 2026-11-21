import type { ReactNode } from 'react';
import styles from './Surface.module.css';

export interface SurfaceProps {
  title?: string;
  muted?: boolean;
  children?: ReactNode;
}

export function Surface({ title, muted = false, children }: SurfaceProps) {
  return (
    <section className={`${styles.surface} ${muted ? styles.muted : ''}`}>
      {title ? <h2 className={styles.title}>{title}</h2> : null}
      <div className={styles.body}>{children}</div>
    </section>
  );
}
