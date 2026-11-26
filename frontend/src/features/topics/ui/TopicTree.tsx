"use client";

import { useCallback, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import type { TopicNodeOut } from "@/entities/document";
import {
  getTopicSelectionState,
  getVisibleNodes,
  findVisibleNodeIndex,
  getNextVisibleIndex,
  getPreviousVisibleIndex,
  getFirstVisibleIndex,
  getLastVisibleIndex,
  getParentVisibleIndex,
  getFirstChildVisibleIndex,
  toggleExpandedFn,
} from "@/features/topics/model/tree";
import styles from "./TopicTree.module.css";

interface TopicTreeProps {
  topics: TopicNodeOut[];
  selectedIds: Set<string>;
  onToggle: (id: string, checked: boolean) => void;
  disabled?: boolean;
}

export function TopicTree({
  topics,
  selectedIds,
  onToggle,
  disabled = false,
}: TopicTreeProps) {
  const t = useTranslations("topics");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const treeRef = useRef<HTMLUListElement>(null);

  // Initialize expandedIds with root topics that have children
  const initialExpanded = new Set<string>();
  for (const topic of topics) {
    if (topic.children.length > 0) {
      initialExpanded.add(topic.id);
    }
  }

  // Compute visible nodes for keyboard navigation
  const visibleNodes = getVisibleNodes(
    topics,
    expandedIds.size > 0 ? expandedIds : initialExpanded
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (disabled || !focusedId) return;

      const focusedIndex = findVisibleNodeIndex(visibleNodes, focusedId);
      if (focusedIndex === -1) return;

      let nextFocusedId: string | null = null;
      let preventDefault = false;

      switch (e.key) {
        case "ArrowDown": {
          const nextIndex = getNextVisibleIndex(visibleNodes, focusedIndex);
          nextFocusedId = visibleNodes[nextIndex]?.topic.id ?? null;
          preventDefault = true;
          break;
        }
        case "ArrowUp": {
          const prevIndex = getPreviousVisibleIndex(visibleNodes, focusedIndex);
          nextFocusedId = visibleNodes[prevIndex]?.topic.id ?? null;
          preventDefault = true;
          break;
        }
        case "ArrowRight": {
          const focusedIndex = findVisibleNodeIndex(visibleNodes, focusedId);
          const focusedNode = visibleNodes[focusedIndex];
          // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
          if (focusedNode && focusedNode.topic.children.length > 0) {
            if (!expandedIds.has(focusedNode.topic.id)) {
              // Expand the node
              setExpandedIds((prev) =>
                toggleExpandedFn(prev, focusedNode.topic.id)
              );
            } else {
              // Move to first child
              const childIndex = getFirstChildVisibleIndex(
                visibleNodes,
                focusedIndex
              );
              nextFocusedId = visibleNodes[childIndex]?.topic.id ?? null;
            }
          }
          preventDefault = true;
          break;
        }
        case "ArrowLeft": {
          const focusedIndex = findVisibleNodeIndex(visibleNodes, focusedId);
          const focusedNode =
            focusedIndex >= 0 ? visibleNodes[focusedIndex] : null;
          if (
            focusedNode &&
            focusedNode.topic.children.length > 0 &&
            expandedIds.has(focusedNode.topic.id)
          ) {
            // Collapse the node
            setExpandedIds((prev) =>
              toggleExpandedFn(prev, focusedNode.topic.id)
            );
          } else {
            // Move to parent
            const parentIndex = getParentVisibleIndex(
              visibleNodes,
              focusedIndex
            );
            if (parentIndex !== focusedIndex) {
              nextFocusedId = visibleNodes[parentIndex]?.topic.id ?? null;
            }
          }
          preventDefault = true;
          break;
        }
        case "Home": {
          nextFocusedId =
            visibleNodes[getFirstVisibleIndex(visibleNodes)]?.topic.id ?? null;
          preventDefault = true;
          break;
        }
        case "End": {
          nextFocusedId =
            visibleNodes[getLastVisibleIndex(visibleNodes)]?.topic.id ?? null;
          preventDefault = true;
          break;
        }
        case " ": // Space
        case "Enter": {
          // Toggle checkbox
          const focusedNode =
            visibleNodes[findVisibleNodeIndex(visibleNodes, focusedId)];
          // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
          if (focusedNode) {
            // The checkbox onChange will handle the actual toggle
            const checkbox = treeRef.current?.querySelector(
              `input[type="checkbox"][data-topic-id="${focusedNode.topic.id}"]`
            ) as HTMLInputElement | null;
            if (checkbox) {
              checkbox.click();
            }
          }
          preventDefault = true;
          break;
        }
      }

      if (nextFocusedId && nextFocusedId !== focusedId) {
        setFocusedId(nextFocusedId);
        // Scroll the new focused element into view
        requestAnimationFrame(() => {
          const element = treeRef.current?.querySelector(
            `[data-topic-id="${nextFocusedId}"]`
          ) as HTMLElement | null;
          element?.scrollIntoView({ block: "nearest" });
        });
      }

      if (preventDefault) {
        e.preventDefault();
      }
    },
    [disabled, expandedIds, focusedId, visibleNodes]
  );

  // Set initial focus to first item
  const firstItemId = visibleNodes[0]?.topic.id;

  if (topics.length === 0) {
    return (
      <div className={styles.empty} role="status">
        <p>{t("empty")}</p>
      </div>
    );
  }

  return (
    <ul
      ref={treeRef}
      className={styles.tree}
      role="tree"
      aria-label={t("title")}
      onKeyDown={handleKeyDown}
    >
      {topics.map((topic) => (
        <TopicNodeItem
          key={topic.id}
          topic={topic}
          selectedIds={selectedIds}
          onToggle={onToggle}
          disabled={disabled}
          depth={0}
          expandedIds={expandedIds.size > 0 ? expandedIds : initialExpanded}
          setExpandedIds={setExpandedIds}
          setFocusedId={setFocusedId}
          focusedId={focusedId}
          firstItemId={firstItemId}
        />
      ))}
    </ul>
  );
}

interface TopicNodeItemProps {
  topic: TopicNodeOut;
  selectedIds: Set<string>;
  onToggle: (id: string, checked: boolean) => void;
  disabled: boolean;
  depth: number;
  expandedIds: Set<string>;
  setExpandedIds: React.Dispatch<React.SetStateAction<Set<string>>>;
  setFocusedId: React.Dispatch<React.SetStateAction<string | null>>;
  focusedId: string | null;
  firstItemId: string | null;
}

function TopicNodeItem({
  topic,
  selectedIds,
  onToggle,
  disabled,
  depth,
  expandedIds,
  setExpandedIds,
  setFocusedId,
  focusedId,
  firstItemId,
}: TopicNodeItemProps) {
  const t = useTranslations("topics");
  const checkboxId = useId();
  const hasChildren = topic.children.length > 0;
  const isExpanded = expandedIds.has(topic.id);
  const selectionState = getTopicSelectionState(topic.id, selectedIds, [topic]); // Simplified for now
  const isSelected = selectedIds.has(topic.id);
  const isIndeterminate = selectionState === "indeterminate";
  const isFocused = focusedId === topic.id;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;
    onToggle(topic.id, e.target.checked);
  };

  const handleCheckboxKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === " " || e.key === "Enter") {
      e.stopPropagation(); // Prevent tree from handling space/enter
    }
  };

  const handleFocus = () => {
    setFocusedId(topic.id);
  };

  const handleBlur = () => {
    // Keep focus for keyboard navigation
  };

  return (
    <li
      className={styles.item}
      style={{ "--depth": depth } as React.CSSProperties}
      role="treeitem"
      aria-expanded={hasChildren ? isExpanded : undefined}
      data-topic-id={topic.id}
    >
      <label
        className={`${styles.label} ${isFocused ? styles.focused : ""}`}
        htmlFor={checkboxId}
      >
        <input
          type="checkbox"
          id={checkboxId}
          className={styles.checkbox}
          checked={isSelected}
          onChange={handleChange}
          onKeyDown={handleCheckboxKeyDown}
          onFocus={handleFocus}
          onBlur={handleBlur}
          disabled={disabled}
          aria-checked={isIndeterminate ? "mixed" : isSelected}
          ref={(el) => {
            if (el) el.indeterminate = isIndeterminate;
          }}
          data-topic-id={topic.id}
        />
        <span className={styles.title}>{topic.title}</span>
        <span
          className={styles.cost}
          aria-label={t("costLabel", { cost: topic.tokens })}
        >
          {topic.tokens}
        </span>
      </label>
      {hasChildren && (
        <>
          <button
            type="button"
            className={styles.expandButton}
            onClick={() => {
              setExpandedIds((prev) => toggleExpandedFn(prev, topic.id));
            }}
            aria-expanded={isExpanded}
            aria-controls={`children-${topic.id}`}
            aria-label={isExpanded ? t("collapse") : t("expand")}
          >
            {isExpanded ? "−" : "+"}
          </button>
          <ul
            id={`children-${topic.id}`}
            className={styles.children}
            role="group"
            hidden={!isExpanded}
          >
            {topic.children.map((child) => (
              <TopicNodeItem
                key={child.id}
                topic={child}
                selectedIds={selectedIds}
                onToggle={onToggle}
                disabled={disabled}
                depth={depth + 1}
                expandedIds={expandedIds}
                setExpandedIds={setExpandedIds}
                setFocusedId={setFocusedId}
                focusedId={focusedId}
                firstItemId={firstItemId}
              />
            ))}
          </ul>
        </>
      )}
    </li>
  );
}
