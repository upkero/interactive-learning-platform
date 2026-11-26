"use client";

import { useMemo } from "react";
import { Link } from "@/shared/i18n/navigation";
import { useFormatter, useTranslations } from "next-intl";
import {
  useMaterials,
  type MaterialOut,
  getMaterialRoute,
} from "@/entities/document";
import { ApiError } from "@/shared/api/errors";
import styles from "./DocumentList.module.css";

type Scope = "mine" | "shared" | "all";

interface DocumentListProps {
  scope?: Scope;
}

const STATUS_STYLES: Record<MaterialOut["status"], string> = {
  uploaded: "status-parsing",
  parsing: "status-parsing",
  parsed: "status-topics",
  generating: "status-generating",
  done: "status-ready",
  failed: "status-error",
};

function getStatusLabel(
  t: ReturnType<typeof useTranslations>,
  doc: MaterialOut
): string {
  const { status, parts_published, parts_total } = doc;
  if (status === "generating") {
    return t(`status.${status}`, {
      published: parts_published,
      total: parts_total,
    });
  }
  return t(`status.${status}`);
}

function getRoleLabel(
  t: ReturnType<typeof useTranslations>,
  doc: MaterialOut
): string {
  if (doc.role === "owner") {
    return t("ownerLabel");
  }
  return t("sharedByLabel", { email: doc.shared_by_email || "—" });
}

export function DocumentList({ scope = "mine" }: DocumentListProps) {
  const t = useTranslations("materials");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");
  const tEmpty = useTranslations("empty");
  const format = useFormatter();

  // For "all" scope, we need to fetch both mine and shared
  const mineQuery = useMaterials("mine");
  const sharedQuery = useMaterials("shared");

  const isPending = mineQuery.isPending || sharedQuery.isPending;
  const isError = mineQuery.isError || sharedQuery.isError;
  const error = mineQuery.error || sharedQuery.error;

  // Combine and deduplicate documents for "all" scope
  const documents = useMemo(() => {
    if (scope === "mine") return mineQuery.data || [];
    if (scope === "shared") return sharedQuery.data || [];

    // scope === "all"
    const mine = mineQuery.data || [];
    const shared = sharedQuery.data || [];
    const seen = new Set<string>();
    const combined: MaterialOut[] = [];

    for (const doc of [...mine, ...shared]) {
      if (!seen.has(doc.document_id)) {
        seen.add(doc.document_id);
        combined.push(doc);
      }
    }

    // Sort by updated_at descending
    combined.sort(
      (a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
    return combined;
  }, [scope, mineQuery.data, sharedQuery.data]);

  if (isPending) {
    return (
      <div
        className={styles.skeletonList}
        role="status"
        aria-label={tCommon("loading")}
      >
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className={styles.skeletonRow}>
            <div className={styles.skeletonCell} style={{ width: "30%" }} />
            <div className={styles.skeletonCell} style={{ width: "15%" }} />
            <div className={styles.skeletonCell} style={{ width: "20%" }} />
            <div className={styles.skeletonCell} style={{ width: "15%" }} />
            <div className={styles.skeletonCell} style={{ width: "10%" }} />
            <div className={styles.skeletonCell} style={{ width: "10%" }} />
          </div>
        ))}
      </div>
    );
  }

  if (isError) {
    const message =
      error instanceof ApiError
        ? tErrors(error.code)
        : tErrors("unknown_error");

    return (
      <div className={styles.errorState} role="alert">
        <p className={styles.errorMessage}>{message}</p>
        <button
          type="button"
          className={styles.retryButton}
          onClick={() => void mineQuery.refetch()}
        >
          {tCommon("retry")}
        </button>
      </div>
    );
  }

  if (documents.length === 0) {
    let emptyKey: string;
    let actionLink: React.ReactNode | null = null;

    if (scope === "shared") {
      emptyKey = "materialsShared";
    } else if (scope === "mine") {
      emptyKey = "materialsMine";
      actionLink = (
        <Link href="/upload" className={styles.emptyAction}>
          {t("uploadButton")}
        </Link>
      );
    } else {
      emptyKey = "materialsAll";
      actionLink = (
        <Link href="/upload" className={styles.emptyAction}>
          {t("uploadButton")}
        </Link>
      );
    }

    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyText}>{tEmpty(emptyKey)}</p>
        {actionLink}
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table} role="grid">
        <thead>
          <tr>
            <th scope="col" className={styles.headerCell}>
              {t("titleLabel")}
            </th>
            <th scope="col" className={styles.headerCell}>
              {t("partsLabel")}
            </th>
            <th scope="col" className={styles.headerCell}>
              {t("statusLabel")}
            </th>
            <th scope="col" className={styles.headerCell}>
              {t("roleLabel")}
            </th>
            <th scope="col" className={styles.headerCell}>
              {t("createdAtLabel")}
            </th>
            <th scope="col" className={styles.headerCell}>
              {t("actionsLabel")}
            </th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <DocumentRow key={doc.document_id} doc={doc} format={format} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface DocumentRowProps {
  doc: MaterialOut;
  format: ReturnType<typeof useFormatter>;
}

function DocumentRow({ doc, format }: DocumentRowProps) {
  const t = useTranslations("materials");
  const tCommon = useTranslations("common");

  const statusStyle = STATUS_STYLES[doc.status];
  const route = getMaterialRoute(doc);
  const statusLabel = getStatusLabel(t, doc);
  const roleLabel = getRoleLabel(t, doc);
  const formattedDate = format.dateTime(new Date(doc.updated_at), {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  const isOwner = doc.role === "owner";

  return (
    <tr className={styles.row}>
      <td className={styles.cell}>
        <Link href={route} className={styles.titleLink}>
          {doc.title}
          {doc.role === "shared" && (
            <span className={styles.sharedBadge} aria-label={t("sharedLabel")}>
              {t("sharedLabel")}
            </span>
          )}
        </Link>
      </td>
      <td className={styles.cell}>
        <span className={styles.partsCount}>
          {doc.parts_published}/{doc.parts_total}
        </span>
      </td>
      <td className={styles.cell}>
        <span className={`${styles.statusBadge} ${styles[statusStyle]}`}>
          {statusLabel}
        </span>
      </td>
      <td className={styles.cell}>
        <span className={styles.roleBadge}>{roleLabel}</span>
      </td>
      <td className={styles.cell}>
        <time dateTime={doc.updated_at}>{formattedDate}</time>
      </td>
      <td className={styles.cell}>
        <div className={styles.actions}>
          <Link
            href={route}
            className={styles.actionLink}
            aria-label={`${t("actionsLabel")}: ${doc.title}`}
          >
            {tCommon("next")}
          </Link>
          {isOwner && (
            <Link
              href={`/share?document=${doc.document_id}`}
              className={styles.actionLink}
              aria-label={`${t("shareAction")}: ${doc.title}`}
            >
              {t("shareAction")}
            </Link>
          )}
        </div>
      </td>
    </tr>
  );
}
