import type { ReactNode } from 'react';
import styles from './SummaryList.module.css';

export interface SummaryItem {
  term: ReactNode;
  description: ReactNode;
}

export function SummaryList({ items }: { items: SummaryItem[] }) {
  return (
    <dl className={styles.list}>
      {items.map((item, index) => (
        <div className={styles.row} key={index}>
          <dt className={styles.term}>{item.term}</dt>
          <dd className={styles.description}>{item.description}</dd>
        </div>
      ))}
    </dl>
  );
}
