"use client";

import { useTranslations } from "next-intl";
import styles from "./KeyTerms.module.css";

interface KeyTerm {
  term: string;
  definition: string;
}

export function KeyTerms({ terms }: { terms: KeyTerm[] }) {
  const t = useTranslations("progress");

  if (terms.length === 0) {
    return (
      <p className={styles.emptyKeyTerms} role="status">
        {t("noKeyTermsYet")}
      </p>
    );
  }

  return (
    <dl className={styles.keyTermsList} role="list">
      {terms.map((kt, index) => (
        <div key={index} className={styles.keyTermItem}>
          <dt className={styles.keyTermName}>{kt.term}</dt>
          <dd className={styles.keyTermDef}>{kt.definition}</dd>
        </div>
      ))}
    </dl>
  );
}
