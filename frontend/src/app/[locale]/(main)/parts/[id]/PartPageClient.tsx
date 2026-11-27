"use client";

import { useState } from "react";
import { PartView } from "@/features/part-view";
import { ReportButton } from "@/features/widget-report";
import { ShareDialog } from "@/features/share";

interface PartPageClientProps {
  partId: string;
}

export function PartPageClient({ partId }: PartPageClientProps) {
  const [shareOpen, setShareOpen] = useState(false);

  return (
    <>
      <PartView
        partId={partId}
        renderWidgetActions={(widgetId, partId) => (
          <ReportButton widgetId={widgetId} partId={partId} />
        )}
        renderQuiz={(quiz) => (
          <div className="inline-quiz-placeholder">
            <p>Quiz: {quiz.key}</p>
            <p>Use the "Check yourself" link below to take the quiz.</p>
          </div>
        )}
        renderShareAction={() => {
          return (
            <button
              type="button"
              onClick={() => {
                setShareOpen(true);
              }}
              aria-label="Share"
            >
              Share
            </button>
          );
        }}
      />
      <ShareDialog
        documentId={partId}
        isOpen={shareOpen}
        onClose={() => {
          setShareOpen(false);
        }}
      />
    </>
  );
}
