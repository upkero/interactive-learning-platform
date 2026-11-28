"use client";

import { useCallback, useMemo, useState, useEffect } from "react";
import { useRouter, useSearchParams } from "@/shared/i18n/navigation-client";
import { useTranslations } from "next-intl";
import { useDebouncedValue } from "@/shared/lib/use-debounced-value";
import { useTopics, usePlan } from "@/features/topics/api";
import { useDocumentStatusGuard } from "@/entities/document";
import { ApiError } from "@/shared/api/errors";
import { TopicTree } from "./TopicTree";
import { TopicSummary } from "./TopicSummary";
import { ActionLink } from "@/shared/ui/action-link/ActionLink";
import { PageShell } from "@/shared/ui/page-shell/PageShell";
import { Surface } from "@/shared/ui/surface/Surface";
import type { TopicNodeOut } from "@/entities/document";
import {
  parseTopicsParam,
  filterValidTopicIds,
  serializeTopicsParam,
} from "@/shared/lib/urlParams";
import styles from "./TopicsFeature.module.css";

type TopicNode = TopicNodeOut;

export function TopicsFeature({ documentId }: { documentId: string }) {
  const t = useTranslations("topics");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");

  const router = useRouter();
  const searchParams = useSearchParams();

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [initializedFromUrl, setInitializedFromUrl] = useState(false);

  const topicsQuery = useTopics(documentId);
  const debouncedSelectedIds = useDebouncedValue<string[]>(
    Array.from(selectedIds),
    300
  );
  const planQuery = usePlan(
    documentId,
    debouncedSelectedIds.length > 0 ? debouncedSelectedIds : null
  );

  // Centralized status guard - topics step allows 'parsed' status
  const {
    isLoading,
    error,
    hasRedirected: guardRedirected,
  } = useDocumentStatusGuard({
    documentId,
    currentStep: "topics",
  });

  // Use topicsQuery.data directly for memoization to avoid new array reference each render
  const memoizedTopics: TopicNode[] = useMemo(
    () => topicsQuery.data ?? [],
    [topicsQuery.data]
  );

  // Initialize selectedIds from URL once when topics are loaded
  useEffect(() => {
    if (
      !initializedFromUrl &&
      topicsQuery.data &&
      topicsQuery.data.length > 0
    ) {
      const urlTopicIds = parseTopicsParam(searchParams);
      if (urlTopicIds.length > 0) {
        const validIds = filterValidTopicIds(urlTopicIds, topicsQuery.data);
        setSelectedIds(new Set(validIds));
      }
      setInitializedFromUrl(true);
    }
  }, [initializedFromUrl, topicsQuery.data, searchParams]);

  // Derive selected count from plan (server-authoritative)
  const selectedCount = planQuery.data?.cost ?? 0;
  const isOverQuota = planQuery.data
    ? planQuery.data.cost > planQuery.data.available
    : false;
  const canProceed = selectedCount > 0 && !isOverQuota && !planQuery.isLoading;

  // Use memoizedTopics for all references to avoid type issues
  const topics = memoizedTopics;

  // Show quota_exceeded error if coming from questions page
  const showQuotaError = searchParams.get("error") === "quota_exceeded";

  const handleNext = useCallback(() => {
    if (!canProceed) return;

    const selectedTopicIds = Array.from(selectedIds);
    const encodedTopics = serializeTopicsParam(selectedTopicIds);
    router.push(`/documents/${documentId}/questions?topics=${encodedTopics}`);
  }, [canProceed, documentId, router, selectedIds]);

  const handleTopicToggle = useCallback(
    (id: string, checked: boolean) => {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        if (checked) {
          // We need to add all descendants - use the topics tree
          const topic = findTopicById(memoizedTopics, id);
          if (topic) {
            const allIds = collectAllIds(topic);
            for (const topicId of allIds) {
              next.add(topicId);
            }
          }
        } else {
          // Remove all descendants
          const topic = findTopicById(memoizedTopics, id);
          if (topic) {
            const allIds = collectAllIds(topic);
            for (const topicId of allIds) {
              next.delete(topicId);
            }
          }
        }
        return next;
      });
    },
    [memoizedTopics]
  );

  const handleSelectAll = useCallback(() => {
    const allIds = collectAllIdsArray(memoizedTopics);
    setSelectedIds(new Set(allIds));
  }, [memoizedTopics]);

  const handleDeselectAll = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const handleRetryTopics = useCallback(() => {
    void topicsQuery.refetch();
  }, [topicsQuery]);

  // Loading state
  if (isLoading) {
    return (
      <PageShell title={t("title")}>
        <TopicsSkeleton tCommon={tCommon} />
      </PageShell>
    );
  }

  // Error state for topics
  if (topicsQuery.isError) {
    const message =
      topicsQuery.error instanceof ApiError
        ? tErrors(topicsQuery.error.code)
        : tErrors("unknown_error");

    return (
      <PageShell title={t("title")}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <p className={styles.errorMessage}>{message}</p>
            <button
              type="button"
              className={styles.retryButton}
              onClick={handleRetryTopics}
            >
              {tCommon("retry")}
            </button>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // Error state for guard
  if (error) {
    return (
      <PageShell title={t("title")}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <p className={styles.errorMessage}>
              {tErrors("document_not_found")}
            </p>
            <ActionLink
              href="/materials"
              variant="secondary"
              className={styles.retryButton}
            >
              {tCommon("back")}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // Empty topics - M-17.1: allow proceeding as single topic
  if (topics.length === 0) {
    return (
      <PageShell title={t("title")}>
        <Surface title={t("planPreviewTitle")}>
          <p className={styles.emptyText}>{t("singleTopicNote")}</p>
        </Surface>
        <div className={styles.actions}>
          <ActionLink href="/materials" variant="secondary">
            {tCommon("back")}
          </ActionLink>
          <ActionLink
            href={`/documents/${documentId}/questions`}
            variant="primary"
            className={styles.proceedButton}
          >
            {tCommon("next")}
          </ActionLink>
        </div>
      </PageShell>
    );
  }

  if (guardRedirected) {
    return null;
  }

  return (
    <PageShell
      title={t("title")}
      actions={
        <ActionLink
          href={`/documents/${documentId}/questions?topics=${serializeTopicsParam(Array.from(selectedIds))}`}
          variant="primary"
          onClick={handleNext}
          disabled={!canProceed || planQuery.isLoading}
          aria-disabled={!canProceed || planQuery.isLoading}
        >
          {planQuery.isLoading ? tCommon("loading") : tCommon("next")}
        </ActionLink>
      }
    >
      <Surface title={t("planPreviewTitle")}>
        <div className={styles.toolbar}>
          <div className={styles.toolbarActions}>
            <button
              type="button"
              className={styles.toolbarButton}
              onClick={handleSelectAll}
              disabled={selectedCount === topics.length}
            >
              {t("selectAll")}
            </button>
            <button
              type="button"
              className={styles.toolbarButton}
              onClick={handleDeselectAll}
              disabled={selectedCount === 0}
            >
              {t("deselectAll")}
            </button>
          </div>
        </div>

        <TopicTree
          topics={topics}
          selectedIds={selectedIds}
          onToggle={handleTopicToggle}
          disabled={planQuery.isLoading}
        />
      </Surface>

      <TopicSummary
        plan={planQuery.data ?? null}
        planLoading={planQuery.isLoading}
        planError={planQuery.isError}
        hasSelection={selectedCount > 0}
      />

      {showQuotaError && (
        <div className={styles.quotaErrorBanner} role="alert">
          {tErrors("quota_exceeded")}
        </div>
      )}
    </PageShell>
  );
}

// Helper functions
function findTopicById(topics: TopicNode[], id: string): TopicNode | undefined {
  for (const topic of topics) {
    if (topic.id === id) return topic;
    if (topic.children.length > 0) {
      const found = findTopicById(topic.children, id);
      if (found) return found;
    }
  }
  return undefined;
}

function collectAllIds(node: TopicNode): string[] {
  const ids: string[] = [node.id];
  for (const child of node.children) {
    ids.push(...collectAllIds(child));
  }
  return ids;
}

function collectAllIdsArray(topics: TopicNode[]): string[] {
  const ids: string[] = [];
  for (const topic of topics) {
    ids.push(...collectAllIds(topic));
  }
  return ids;
}

function TopicsSkeleton({
  tCommon,
}: {
  tCommon: ReturnType<typeof import("next-intl").useTranslations>;
}) {
  return (
    <div
      className={styles.skeleton}
      role="status"
      aria-label={tCommon("loading")}
    >
      <Surface>
        <div className={styles.skeletonToolbar}>
          <div className={styles.skeletonButton} />
          <div className={styles.skeletonButton} />
        </div>
        <div className={styles.skeletonTree}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className={styles.skeletonItem}>
              <div className={styles.skeletonCheckbox} />
              <div className={styles.skeletonTitle} style={{ width: "60%" }} />
              <div className={styles.skeletonCost} />
            </div>
          ))}
        </div>
      </Surface>
      <div className={styles.skeletonSummary}>
        <Surface>
          <div className={styles.skeletonRow}>
            <div className={styles.skeletonLabel} />
            <div className={styles.skeletonValue} />
          </div>
          <div className={styles.skeletonRow}>
            <div className={styles.skeletonLabel} />
            <div className={styles.skeletonValue} />
          </div>
          <div className={styles.skeletonRow}>
            <div className={styles.skeletonLabel} />
            <div className={styles.skeletonValue} />
          </div>
        </Surface>
      </div>
    </div>
  );
}
