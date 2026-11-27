"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkDirective from "remark-directive";
import rehypeSlug from "rehype-slug";
import { remarkGraspDirectives } from "../lib/remark-grasp-directives";
import { WidgetBlock } from "@/entities/widget";
import { PartImage } from "@/entities/part";
import type {
  ImageOut,
  ChoiceQuiz,
  OrderingQuiz,
  NumericQuiz,
} from "@/entities/part";
import type {
  WidgetFallback,
  ConfigWidget,
  CodeWidget,
} from "@/entities/widget";
import styles from "./PartMarkdown.module.css";

export interface WidgetSlot {
  key: string;
  title: string;
  status: "pending" | "fallback" | "ready";
  fallback?: WidgetFallback;
  config?: ConfigWidget;
  code?: CodeWidget;
}

interface PartMarkdownProps {
  markdown: string;
  widgets: Record<string, WidgetSlot>;
  images: Record<string, ImageOut>;
  quizzes: (ChoiceQuiz | OrderingQuiz | NumericQuiz)[];
  renderQuiz?: (
    quiz: ChoiceQuiz | OrderingQuiz | NumericQuiz
  ) => React.ReactNode;
  renderWidgetActions?: (widgetId: string, partId: string) => React.ReactNode;
  partId: string;
}

function QuizPlaceholder({ quizRef }: { quizRef: string }) {
  return (
    <div
      className={styles.quizPlaceholder}
      role="note"
      aria-label="Quiz placeholder"
    >
      <p>Quiz: {quizRef}</p>
    </div>
  );
}

export function PartMarkdown({
  markdown,
  widgets,
  images,
  quizzes,
  renderQuiz,
  renderWidgetActions,
  partId,
}: PartMarkdownProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const components: any = {
    "grasp-widget": ({ dataKey }: { dataKey: string }) => {
      const widget = widgets[dataKey];
      // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
      if (!widget) {
        return (
          <div className={styles.missingWidget} role="note">
            Widget not found: {dataKey}
          </div>
        );
      }
      return (
        <WidgetBlock
          key={widget.key}
          slot={widget}
          images={images}
          renderActions={renderWidgetActions}
          partId={partId}
        />
      );
    },
    "grasp-image": ({ dataKey }: { dataKey: string }) => {
      const image = images[dataKey];
      // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
      if (!image) {
        return (
          <div className={styles.missingImage} role="note">
            Image not found: {dataKey}
          </div>
        );
      }
      return <PartImage key={dataKey} image={image} />;
    },
    "grasp-quiz": ({ dataKey }: { dataKey: string }) => {
      const quiz = quizzes.find((q) => q.key === dataKey);
      if (!quiz) {
        return <QuizPlaceholder quizRef={dataKey} />;
      }
      if (renderQuiz) {
        return renderQuiz(quiz);
      }
      return <QuizPlaceholder quizRef={dataKey} />;
    },
  };

  return (
    <div className={styles.markdownContainer}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkDirective, remarkGraspDirectives]}
        rehypePlugins={[rehypeSlug]}
        // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
        components={components}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
