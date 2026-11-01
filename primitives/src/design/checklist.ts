export type ChecklistSeverity = "blocker" | "major" | "minor";

export interface ChecklistRule {
  /** Stable identifier referenced by the generator and judge in issues[]. */
  id: string;
  severity: ChecklistSeverity;
  /** English wording is intentional: generator and judge prompts are in English. */
  rule: string;
}

/**
 * Rules shared by human review, the code generator, and the judge.
 * IDs are part of the public solver contract: never rename or reuse them.
 */
export const designChecklist: readonly ChecklistRule[] = [
  {
    id: "DS-01",
    severity: "blocker",
    rule: "Colors, spacing, radii and durations use only var(--g-*) tokens; no hex, rgb(), or hardcoded layout values.",
  },
  {
    id: "DS-02",
    severity: "blocker",
    rule: "The widget is readable in both light and dark themes; screenshots for both themes are provided.",
  },
  {
    id: "DS-03",
    severity: "blocker",
    rule: "All visible UI text comes from labels or params; no hardcoded user-facing strings are present.",
  },
  {
    id: "DS-04",
    severity: "major",
    rule: "Interactive controls use @grasp/primitives/ui (Button, Slider, Toggle, ModeTabs, StepControls) instead of local equivalents.",
  },
  {
    id: "DS-05",
    severity: "major",
    rule: "The widget fits a 320–800 px container without horizontal scrolling or clipped labels.",
  },
  {
    id: "DS-06",
    severity: "major",
    rule: "Text is at least var(--g-text-sm); elements and labels do not overlap.",
  },
  {
    id: "DS-07",
    severity: "major",
    rule: "Active or compared elements use --g-viz-active and a second non-color cue such as an outline or label.",
  },
  {
    id: "DS-08",
    severity: "minor",
    rule: "Animations use var(--g-duration-*) and stop when reduced-motion durations are 0.",
  },
  {
    id: "DS-09",
    severity: "major",
    rule: "Every SVG root has role=\"img\" and an aria-label; step captions are announced in an aria-live region.",
  },
  {
    id: "DS-10",
    severity: "blocker",
    rule: "The widget renders without console errors for every provided parameter set.",
  },
];
