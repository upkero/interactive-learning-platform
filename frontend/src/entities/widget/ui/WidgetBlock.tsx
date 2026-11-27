"use client";

import { ErrorBoundary } from "react-error-boundary";
import { getPrimitive } from "@grasp/primitives/registry";
import { WidgetPending } from "./WidgetPending";
import { WidgetFallback } from "./WidgetFallback";
import { WidgetFrame } from "./WidgetFrame";
import type {
  ConfigWidget,
  CodeWidget,
  WidgetFallback as WidgetFallbackType,
} from "@/entities/widget";
import type { ImageOut } from "@/entities/part";
import styles from "./WidgetBlock.module.css";

interface WidgetBlockProps {
  slot: {
    key: string;
    title: string;
    status: "pending" | "fallback" | "ready";
    fallback?: WidgetFallbackType;
    config?: ConfigWidget;
    code?: CodeWidget;
  };
  images: Record<string, ImageOut>;
  renderActions?: (widgetId: string, partId: string) => React.ReactNode;
  partId: string;
}

function ConfigWidgetRenderer({ widget }: { widget: ConfigWidget }) {
  const definition = getPrimitive(widget.primitive_id);

  if (!definition) {
    throw new Error(`Primitive ${widget.primitive_id} not found`);
  }

  const result = definition.paramsSchema.safeParse(widget.params);
  if (!result.success) {
    throw new Error(
      `Invalid params for primitive ${widget.primitive_id}: ${result.error.message}`
    );
  }

  const Labels = definition.labelKeys.reduce<Record<string, string>>(
    (acc, key) => {
      acc[key] = key;
      return acc;
    },
    {}
  );

  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-assignment
  const Component = definition.component as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-assignment
  const mode = widget.mode as any;

  return (
    <Component
      params={result.data} // eslint-disable-line @typescript-eslint/no-unsafe-assignment
      mode={mode} // eslint-disable-line @typescript-eslint/no-unsafe-assignment
      labels={Labels}
    />
  );
}

function CodeWidgetRenderer({
  widget,
  title,
}: {
  widget: CodeWidget;
  title: string;
}) {
  return <WidgetFrame widget={widget} title={title} />;
}

function FallbackRenderer({
  slot,
  images,
  title,
}: {
  slot: WidgetBlockProps["slot"];
  images: Record<string, ImageOut>;
  title: string;
}) {
  return (
    <WidgetFallback
      fallback={slot.fallback as WidgetFallbackType}
      images={images}
      title={title}
    />
  );
}

export function WidgetBlock({
  slot,
  images,
  renderActions,
  partId,
}: WidgetBlockProps) {
  const widgetId = slot.key;

  const renderContent = () => {
    switch (slot.status) {
      case "pending":
        return <WidgetPending title={slot.title} />;
      case "fallback":
        return (
          <FallbackRenderer slot={slot} images={images} title={slot.title} />
        );
      case "ready":
        if (slot.config) {
          return (
            <ErrorBoundary
              FallbackComponent={({ error }) => {
                console.error("Config widget error:", error);
                return (
                  <FallbackRenderer
                    slot={slot}
                    images={images}
                    title={slot.title}
                  />
                );
              }}
            >
              <ConfigWidgetRenderer widget={slot.config} />
            </ErrorBoundary>
          );
        }
        if (slot.code) {
          return (
            <ErrorBoundary
              FallbackComponent={({ error }) => {
                console.error("Code widget error:", error);
                return (
                  <FallbackRenderer
                    slot={slot}
                    images={images}
                    title={slot.title}
                  />
                );
              }}
            >
              <CodeWidgetRenderer widget={slot.code} title={slot.title} />
            </ErrorBoundary>
          );
        }
        return (
          <WidgetFallback
            fallback={slot.fallback as WidgetFallbackType}
            images={images}
            title={slot.title}
          />
        );
      default:
        return (
          <WidgetFallback
            fallback={slot.fallback as WidgetFallbackType}
            images={images}
            title={slot.title}
          />
        );
    }
  };

  return (
    <figure
      className={styles.figure}
      role="region"
      aria-labelledby={`widget-title-${widgetId}`}
    >
      <figcaption id={`widget-title-${widgetId}`} className={styles.caption}>
        <div className={styles.captionRow}>
          <span className={styles.title}>{slot.title}</span>
          {renderActions && renderActions(widgetId, partId)}
        </div>
      </figcaption>
      <div className={styles.content}>{renderContent()}</div>
    </figure>
  );
}
