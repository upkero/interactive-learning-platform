import { designChecklist, type ChecklistRule } from "./checklist";

export interface ChecklistIssue {
  id: ChecklistRule["id"];
  severity: ChecklistRule["severity"];
}

/**
 * Deterministic preflight for obvious source-level violations.
 * The multimodal judge applies the full checklist to code and screenshots later.
 */
export function findObviousDesignIssues(source: string): ChecklistIssue[] {
  const ids = new Set<string>();
  if (/(#[\da-f]{3,8}\b|rgba?\()/i.test(source)) ids.add("DS-01");
  if (/<(?:button|label|p|span|h[1-6])[^>]*>\s*[A-Za-zА-Яа-я]/.test(source)) {
    ids.add("DS-03");
  }
  if (
    /<(?:button|input|select)\b/.test(source) &&
    !source.includes("@grasp/primitives/ui")
  ) {
    ids.add("DS-04");
  }
  if (/animation(?:-duration)?\s*:/.test(source) && !source.includes("var(--g-duration-")) {
    ids.add("DS-08");
  }
  if (/<svg\b/.test(source) && !/<svg[^>]+role=["']img["'][^>]+aria-label=/.test(source)) {
    ids.add("DS-09");
  }

  return designChecklist
    .filter((rule) => ids.has(rule.id))
    .map(({ id, severity }) => ({ id, severity }));
}
