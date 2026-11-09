/** Sort object keys recursively; preserve semantically ordered arrays. */
export function stableStringify(value: unknown): string {
  return JSON.stringify(
    value,
    (_key, item: unknown) => {
      if (item !== null && typeof item === "object" && !Array.isArray(item)) {
        return Object.fromEntries(
          Object.entries(item).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
        );
      }
      return item;
    },
    2
  );
}
