import type { TopicNodeOut } from "@/entities/document";

export type TopicNode = TopicNodeOut;

/**
 * Collect all topic IDs from the tree into a Set.
 */
export function collectAllTopicIds(
  topics: TopicNode[],
  ids: Set<string> = new Set()
): Set<string> {
  for (const topic of topics) {
    ids.add(topic.id);
    if (topic.children.length > 0) {
      collectAllTopicIds(topic.children, ids);
    }
  }
  return ids;
}

/**
 * Collect all descendant topic IDs for a given topic ID.
 */
export function collectSubtreeIds(
  topicId: string,
  topics: TopicNode[]
): string[] {
  const ids: string[] = [];

  function traverse(nodes: TopicNode[]) {
    for (const topic of nodes) {
      if (topic.id === topicId) {
        collectAllTopicIds(topic.children, new Set(ids));
        return;
      }
      if (topic.children.length > 0) {
        traverse(topic.children);
      }
    }
  }

  traverse(topics);
  return ids;
}

/**
 * Check if a topic is fully selected (all descendants selected).
 */
export function isTopicSelected(
  topicId: string,
  selectedIds: Set<string>,
  topics: TopicNode[]
): boolean {
  const subtreeIds = collectSubtreeIds(topicId, topics);
  return subtreeIds.every((id) => selectedIds.has(id));
}

/**
 * Check if a topic is partially selected (some but not all descendants selected).
 */
export function isTopicPartiallySelected(
  topicId: string,
  selectedIds: Set<string>,
  topics: TopicNode[]
): boolean {
  const subtreeIds = collectSubtreeIds(topicId, topics);
  if (subtreeIds.length === 0) return false;

  const selectedInSubtree = subtreeIds.filter((id) => selectedIds.has(id));
  return (
    selectedInSubtree.length > 0 && selectedInSubtree.length < subtreeIds.length
  );
}

/**
 * Get the selection state for a topic: "checked" | "indeterminate" | "unchecked".
 */
export function getTopicSelectionState(
  topicId: string,
  selectedIds: Set<string>,
  topics: TopicNode[]
): "checked" | "indeterminate" | "unchecked" {
  if (isTopicSelected(topicId, selectedIds, topics)) return "checked";
  if (isTopicPartiallySelected(topicId, selectedIds, topics))
    return "indeterminate";
  return "unchecked";
}

/**
 * Toggle a topic and all its descendants.
 * Returns a new Set with the updated selection.
 */
export function toggleTopicSelection(
  selectedIds: Set<string>,
  topicId: string,
  topics: TopicNode[],
  checked: boolean
): Set<string> {
  const newSelectedIds = new Set(selectedIds);
  const subtreeIds = collectSubtreeIds(topicId, topics);

  if (checked) {
    for (const id of subtreeIds) {
      newSelectedIds.add(id);
    }
  } else {
    for (const id of subtreeIds) {
      newSelectedIds.delete(id);
    }
  }

  return newSelectedIds;
}

/**
 * Get a flat list of all visible nodes (for keyboard navigation).
 * Only includes nodes that are not hidden inside collapsed parents.
 */
export function getVisibleNodes(
  topics: TopicNode[],
  expandedIds: Set<string>,
  depth = 0,
  parentId: string | null = null
): Array<{ topic: TopicNode; depth: number; parentId: string | null }> {
  const visible: Array<{
    topic: TopicNode;
    depth: number;
    parentId: string | null;
  }> = [];

  for (const topic of topics) {
    visible.push({ topic, depth, parentId });

    if (topic.children.length > 0 && expandedIds.has(topic.id)) {
      visible.push(
        ...getVisibleNodes(topic.children, expandedIds, depth + 1, topic.id)
      );
    }
  }

  return visible;
}

/**
 * Toggle expanded state of a topic.
 */
export function toggleExpanded(
  expandedIds: Set<string>,
  topicId: string
): Set<string> {
  const newExpandedIds = new Set(expandedIds);
  if (newExpandedIds.has(topicId)) {
    newExpandedIds.delete(topicId);
  } else {
    newExpandedIds.add(topicId);
  }
  return newExpandedIds;
}

/**
 * Alias for toggleExpanded for backward compatibility.
 */
export const toggleExpandedFn = toggleExpanded;

/**
 * Find the index of a topic in the visible nodes list by ID.
 */
export function findVisibleNodeIndex(
  visibleNodes: Array<{
    topic: TopicNode;
    depth: number;
    parentId: string | null;
  }>,
  topicId: string
): number {
  return visibleNodes.findIndex((node) => node.topic.id === topicId);
}

/**
 * Get the next visible node index (for ArrowDown).
 */
export function getNextVisibleIndex(
  visibleNodes: Array<{
    topic: TopicNode;
    depth: number;
    parentId: string | null;
  }>,
  currentIndex: number
): number {
  return Math.min(currentIndex + 1, visibleNodes.length - 1);
}

/**
 * Get the previous visible node index (for ArrowUp).
 */
export function getPreviousVisibleIndex(
  visibleNodes: Array<{
    topic: TopicNode;
    depth: number;
    parentId: string | null;
  }>,
  currentIndex: number
): number {
  return Math.max(currentIndex - 1, 0);
}

/**
 * Get the first visible node index (for Home).
 */
export function getFirstVisibleIndex(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _visibleNodes: Array<{
    topic: TopicNode;
    depth: number;
    parentId: string | null;
  }>
): number {
  return 0;
}

/**
 * Get the last visible node index (for End).
 */
export function getLastVisibleIndex(
  visibleNodes: Array<{
    topic: TopicNode;
    depth: number;
    parentId: string | null;
  }>
): number {
  return visibleNodes.length - 1;
}

/**
 * Get the parent node index of a given visible node.
 */
export function getParentVisibleIndex(
  visibleNodes: Array<{
    topic: TopicNode;
    depth: number;
    parentId: string | null;
  }>,
  currentIndex: number
): number {
  const currentNode = visibleNodes[currentIndex];
  if (currentNode.parentId === null) return currentIndex;

  // Find the parent node in the visible nodes
  for (let i = currentIndex - 1; i >= 0; i--) {
    if (visibleNodes[i].topic.id === currentNode.parentId) {
      return i;
    }
  }
  return currentIndex;
}

/**
 * Get the first child node index of a given visible node.
 */
export function getFirstChildVisibleIndex(
  visibleNodes: Array<{
    topic: TopicNode;
    depth: number;
    parentId: string | null;
  }>,
  currentIndex: number
): number {
  const currentNode = visibleNodes[currentIndex];
  // The first child would be at the next index if it exists and has depth + 1
  const nextIndex = currentIndex + 1;
  if (
    nextIndex < visibleNodes.length &&
    visibleNodes[nextIndex].depth === currentNode.depth + 1
  ) {
    return nextIndex;
  }
  return currentIndex;
}
