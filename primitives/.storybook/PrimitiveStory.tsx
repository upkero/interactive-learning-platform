import type { ReactNode } from "react";
import type { z } from "zod";

interface PrimitiveStoryProps<T> {
  params: unknown;
  schema: z.ZodType<T>;
  children: (params: T) => ReactNode;
}

/** Renders invalid story args as a readable schema error rather than crashing Storybook. */
export function PrimitiveStory<T>({ params, schema, children }: PrimitiveStoryProps<T>) {
  const parsed = schema.safeParse(params);
  if (!parsed.success) {
    return <pre role="alert">{`Invalid primitive params:\n${parsed.error.issues.map((issue) => `${issue.path.join(".") || "params"}: ${issue.message}`).join("\n")}`}</pre>;
  }
  return <>{children(parsed.data)}</>;
}
