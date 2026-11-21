'use client';

import { useTranslations } from 'next-intl';
import { useId } from 'react';
import type { TopicNodeOut } from '@/entities/document';
import styles from './TopicTree.module.css';

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
  const t = useTranslations('topics');

  if (topics.length === 0) {
    return (
      <div className={styles.empty} role="status">
        <p>{t('empty')}</p>
      </div>
    );
  }

  return (
    <ul className={styles.tree} role="tree" aria-label={t('title')}>
      {topics.map((topic) => (
        <TopicNodeItem
          key={topic.id}
          topic={topic}
          selectedIds={selectedIds}
          onToggle={onToggle}
          disabled={disabled}
          depth={0}
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
}

function TopicNodeItem({
  topic,
  selectedIds,
  onToggle,
  disabled,
  depth,
}: TopicNodeItemProps) {
  const t = useTranslations('topics');
  const checkboxId = useId();
  const hasChildren = topic.children.length > 0;
  const isSelected = selectedIds.has(topic.id);
  const isIndeterminate = hasChildren && !isSelected && isPartiallySelected(topic, selectedIds);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;
    onToggle(topic.id, e.target.checked);
  };

  return (
    <li className={styles.item} style={{ '--depth': depth } as React.CSSProperties} role="treeitem">
      <label className={styles.label} htmlFor={checkboxId}>
        <input
          type="checkbox"
          id={checkboxId}
          className={styles.checkbox}
          checked={isSelected}
          onChange={handleChange}
          disabled={disabled}
          aria-checked={isIndeterminate ? 'mixed' : isSelected}
          ref={(el) => {
            if (el) el.indeterminate = isIndeterminate;
          }}
        />
        <span className={styles.title}>{topic.title}</span>
        <span className={styles.cost} aria-label={t('costLabel', { cost: topic.tokens })}>
          {topic.tokens}
        </span>
      </label>
      {hasChildren && (
        <ul className={styles.children} role="group">
          {topic.children.map((child) => (
            <TopicNodeItem
              key={child.id}
              topic={child}
              selectedIds={selectedIds}
              onToggle={onToggle}
              disabled={disabled}
              depth={depth + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function isPartiallySelected(topic: TopicNodeOut, selectedIds: Set<string>): boolean {
  if (topic.children.length === 0) return false;

  let hasSelected = false;
  let hasUnselected = false;

  for (const child of topic.children) {
    if (selectedIds.has(child.id)) {
      hasSelected = true;
    } else {
      hasUnselected = true;
    }
    if (hasSelected && hasUnselected) return true;
    if (isPartiallySelected(child, selectedIds)) return true;
  }

  return hasSelected && hasUnselected;
}