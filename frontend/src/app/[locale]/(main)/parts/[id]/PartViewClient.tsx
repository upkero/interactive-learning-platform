"use client";

import { useTranslations } from "next-intl";
import { usePart } from "@/entities/document";
import { ApiError } from "@/shared/api/errors";
import { ActionLink, PageShell, Surface } from "@/shared/ui";
import { DocumentViewClient } from "../../documents/[id]/DocumentViewClient";

export function PartViewClient({ partId }: { partId: string }) {
  const t = useTranslations("viewer");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");
  const part = usePart(partId);

  if (part.data) {
    return (
      <DocumentViewClient
        documentId={part.data.document_id}
        initialPartId={partId}
      />
    );
  }

  return (
    <PageShell title={t("materialTitle")}>
      <Surface>
        {part.isPending ? (
          <p role="status">{tCommon("loading")}</p>
        ) : (
          <div role="alert">
            <p>{tErrors(part.error instanceof ApiError ? part.error.code : "unknown_error")}</p>
            <ActionLink href="/materials" variant="secondary">
              {tCommon("back")}
            </ActionLink>
          </div>
        )}
      </Surface>
    </PageShell>
  );
}
