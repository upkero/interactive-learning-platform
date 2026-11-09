import { action } from "@storybook/addon-actions";
import type { Labels } from "../src/core/labels";
import type {
  AnyPrimitiveDefinition,
  Mode,
  PrimitiveEvent,
} from "../src/core/types";
import en from "../src/i18n/en.json";
import ru from "../src/i18n/ru.json";

export interface PrimitiveStoryProps {
  definition: AnyPrimitiveDefinition;
  example: string;
  mode?: Mode;
  locale?: "en" | "ru";
  params?: unknown;
  onEvent?: (event: PrimitiveEvent) => void;
  translations?: { en: Labels; ru: Labels };
}
const logEvent = action("primitive:event");
const errors = {
  en: {
    invalid: "Invalid primitive parameters",
    unknown: "Unknown primitive example",
  },
  ru: {
    invalid: "Неверные параметры примитива",
    unknown: "Неизвестный пример примитива",
  },
};

/** The same definition, schema and examples used by the resolver catalog. */
export function PrimitiveStory({
  definition,
  example,
  mode,
  locale = "en",
  params,
  onEvent = logEvent,
  translations,
}: PrimitiveStoryProps) {
  const labels = { ...(locale === "ru" ? ru : en), ...translations?.[locale] };
  const selected = definition.examples.find((item) => item.name === example);
  if (!selected)
    return (
      <p role="alert">
        {errors[locale].unknown}: {example}
      </p>
    );
  const parsed = definition.paramsSchema.safeParse(
    params === undefined ? selected.params : params
  );
  if (!parsed.success)
    return (
      <div role="alert">
        <p>{errors[locale].invalid}</p>
        <ul>
          {parsed.error.issues.map((issue, index) => (
            <li key={index}>
              {issue.path.join(".") || "params"}: {issue.message}
            </li>
          ))}
        </ul>
      </div>
    );
  const Component = definition.component;
  return (
    <Component
      key={`${definition.id}:${example}`}
      params={parsed.data}
      mode={mode ?? selected.mode}
      labels={labels}
      onEvent={onEvent}
    />
  );
}
