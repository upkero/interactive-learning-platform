"use client";

import { useTranslations } from "next-intl";
import styles from "./StageLog.module.css";

interface StageLogEntry {
  eventId: string;
  timestamp: number;
  text: string;
}

export function StageLog({ entries }: { entries: StageLogEntry[] }) {
  const t = useTranslations("progress");

  if (entries.length === 0) {
    return (
      <p className={styles.emptyStage} role="status">
        {t("waitingForStages")}
      </p>
    );
  }

  return (
    <div
      className={styles.stageLog}
      role="log"
      aria-live="polite"
      aria-label={t("stageLogTitle")}
    >
      <ul className={styles.stageList} role="list">
        {entries.map((entry) => (
          <li key={entry.eventId} className={styles.stageItem}>
            <time
              className={styles.stageTime}
              dateTime={new Date(entry.timestamp).toISOString()}
            >
              {new Date(entry.timestamp).toLocaleTimeString(undefined, {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </time>
            <span className={styles.stageText}>{entry.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
