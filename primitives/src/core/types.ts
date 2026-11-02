import type { ComponentType } from "react";
import type { z } from "zod";

import type { Labels, LabelVariables } from "./labels";

export const MODES = ["watch", "steps", "tweak", "predict", "break"] as const;
export type Mode = (typeof MODES)[number];

export const MVP_MODES: readonly Mode[] = ["watch", "steps", "predict"];
export const MAX_FRAMES = 200;

export type { Labels, LabelVariables } from "./labels";

export type PrimitiveEvent =
  | { type: "step"; index: number; total: number }
  | { type: "predict"; questionId: string; correct: boolean }
  | { type: "mode"; mode: Mode }
  | { type: "complete" };

export interface PrimitiveProps<Params> {
  params: Params;
  mode: Mode;
  labels: Labels;
  onEvent?: (event: PrimitiveEvent) => void;
}

export interface PredictQuestion {
  id: string;
  promptKey: string;
  promptVars?: LabelVariables;
  options: readonly { id: string; labelKey: string }[];
  correctId: string;
  explanationKey?: string;
}

export interface Frame {
  captionKey: string;
  captionVars?: LabelVariables;
  question?: PredictQuestion;
}

export interface PrimitiveExample<Params> {
  /** Kebab-case name; used as the Storybook story identifier. */
  name: string;
  /** English resolver-style request describing the intended visualization. */
  intent: string;
  mode: Mode;
  params: Params;
}

export interface PrimitiveDefinition<Params> {
  /** Stable kebab-case identifier, for example `array-ops`. */
  id: string;
  /** Semver version; a breaking schema change increments its major version. */
  version: string;
  /** Short English title shown in the catalog. */
  title: string;
  /**
   * English prompt-facing description: what the primitive explains and when to
   * select it. It must name the supported domain concepts and exclusions.
   */
  description: string;
  /** Input schema shared by the resolver, backend catalog, and frontend. */
  paramsSchema: z.ZodType<Params>;
  modes: readonly Mode[];
  component: ComponentType<PrimitiveProps<Params>>;
  /** Two to four realistic, English few-shot examples for the resolver. */
  examples: readonly PrimitiveExample<Params>[];
  /** Translation keys required by this primitive in both locale dictionaries. */
  labelKeys: readonly string[];
}
