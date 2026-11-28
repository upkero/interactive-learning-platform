/**
 * Shared URL parameter utilities for parsing topic IDs from query strings.
 * Used by both topics and questions features to avoid duplication.
 */

/**
 * Parses the `topics` query parameter into an array of topic IDs.
 * Handles empty/invalid values gracefully.
 */
export function parseTopicsParam(searchParams: URLSearchParams): string[] {
  const topicsParam = searchParams.get("topics");
  if (!topicsParam) return [];

  return topicsParam
    .split(",")
    .map((id) => id.trim())
    .filter((id) => id.length > 0);
}

/**
 * Serializes an array of topic IDs into a `topics` query parameter value.
 * Uses URLSearchParams for proper encoding.
 */
export function serializeTopicsParam(topicIds: string[]): string {
  return encodeURIComponent(topicIds.join(","));
}

/**
 * Creates a URLSearchParams object with the topics parameter set.
 * Useful for navigation.
 */
export function createTopicsSearchParams(
  baseParams: URLSearchParams,
  topicIds: string[]
): URLSearchParams {
  const params = new URLSearchParams(baseParams);
  if (topicIds.length > 0) {
    params.set("topics", serializeTopicsParam(topicIds));
  } else {
    params.delete("topics");
  }
  return params;
}

/**
 * Filters topic IDs to only include those that exist in the given topic tree.
 * This prevents invalid/malicious IDs from being used.
 */
export function filterValidTopicIds(
  topicIds: string[],
  topicTree: { id: string; children: unknown[] }[]
): string[] {
  const validIds = new Set<string>();

  function collectIds(nodes: { id: string; children: unknown[] }[]) {
    for (const node of nodes) {
      validIds.add(node.id);
      if (node.children.length > 0) {
        collectIds(node.children as { id: string; children: unknown[] }[]);
      }
    }
  }

  collectIds(topicTree);

  return topicIds.filter((id) => validIds.has(id));
}
