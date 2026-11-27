"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "@/shared/i18n/navigation-client";
import { useTranslations } from "next-intl";
import { useStartGeneration, usePlan } from "@/features/questions/api";
import { useMe, useQuota, useUpdatePreferences } from "@/entities/user";
import { useDocumentStatusGuard } from "@/entities/document";
import { ApiError } from "@/shared/api/errors";
import { ActionLink } from "@/shared/ui/action-link/ActionLink";
import { PageShell } from "@/shared/ui/page-shell/PageShell";
import { Surface } from "@/shared/ui/surface/Surface";
import styles from "./QuestionsFeature.module.css";

type Level = "novice" | "intermediate" | "advanced";
type Depth = "overview" | "standard" | "deep";
type Goal = "refresh" | "exam" | "understand";

interface FormData {
  level: Level;
  depth: Depth;
  goal: Goal;
  notify_by_email: boolean;
}

const LEVELS: { value: Level; labelKey: string }[] = [
  { value: "novice", labelKey: "levelNovice" },
  { value: "intermediate", labelKey: "levelIntermediate" },
  { value: "advanced", labelKey: "levelAdvanced" },
];

const DEPTHS: { value: Depth; labelKey: string }[] = [
  { value: "overview", labelKey: "depthOverview" },
  { value: "standard", labelKey: "depthStandard" },
  { value: "deep", labelKey: "depthDeep" },
];

const GOALS: { value: Goal; labelKey: string }[] = [
  { value: "refresh", labelKey: "goalRefresh" },
  { value: "exam", labelKey: "goalExam" },
  { value: "understand", labelKey: "goalUnderstand" },
];

export function QuestionsFeature({ documentId }: { documentId: string }) {
  const t = useTranslations("questions");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");

  const router = useRouter();
  const searchParams = useSearchParams();

  // Get user preferences for initial form values
  const meQuery = useMe();
  const updatePreferencesMutation = useUpdatePreferences();

  // Get plan data for selected topics
  const topicsParam = searchParams.get("topics") ?? "";
  const selectedTopicIds = useMemo(
    () => topicsParam.split(",").filter(Boolean),
    [topicsParam]
  );
  const topicsPath = `/documents/${documentId}/topics`;
  const selectedTopicsQuery = new URLSearchParams(
    topicsParam ? { topics: topicsParam } : undefined
  ).toString();
  const topicsHref = selectedTopicsQuery
    ? `${topicsPath}?${selectedTopicsQuery}`
    : topicsPath;
  const planQuery = usePlan(
    documentId,
    selectedTopicIds.length > 0 ? selectedTopicIds : null
  );

  const generateMutation = useStartGeneration();
  const quotaQuery = useQuota();

  // Centralized status guard - questions step allows 'parsed' status
  const {
    isLoading,
    error,
    hasRedirected: guardRedirected,
  } = useDocumentStatusGuard({
    documentId,
    currentStep: "questions",
  });

  // Initialize form data from user's last_answers
  const [formData, setFormData] = useState<FormData>({
    level: "intermediate",
    depth: "standard",
    goal: "exam",
    notify_by_email: false,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<ApiError["code"] | null>(null);
  const inFlightRef = useRef(false);

  // Initialize form from meQuery data when available
  useEffect(() => {
    const meData = meQuery.data;
    if (meData?.last_answers) {
      const lastAnswers = meData.last_answers;
      setFormData((prev) => ({
        ...prev,
        level: lastAnswers.level,
        depth: lastAnswers.depth,
        goal: lastAnswers.goal,
      }));
    }
    if (meData?.notify_email !== undefined) {
      setFormData((prev) => ({
        ...prev,
        notify_by_email: meData.notify_email,
      }));
    }
  }, [meQuery.data]);

  const quotaAvailable = quotaQuery.data?.available ?? null;
  const planCost = planQuery.data?.cost ?? selectedTopicIds.length;
  const planAvailable = planQuery.data?.available ?? quotaAvailable;
  const isOverQuota = planAvailable !== null && planCost > planAvailable;
  const canSubmit =
    !isSubmitting && !isOverQuota && selectedTopicIds.length > 0;

  const handleChange = useCallback(
    <K extends keyof FormData>(field: K, value: FormData[K]) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setSubmitError(null);
    },
    []
  );

  const handleBack = useCallback(() => {
    router.push(topicsHref);
  }, [router, topicsHref]);

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;

    // Protection against multiple synchronous clicks
    if (inFlightRef.current || generateMutation.isPending) return;
    inFlightRef.current = true;

    setIsSubmitting(true);
    setSubmitError(null);

    const answers = {
      level: formData.level,
      depth: formData.depth,
      goal: formData.goal,
    };

    // Update notify_email preference if changed
    if (
      meQuery.data &&
      formData.notify_by_email !== meQuery.data.notify_email
    ) {
      try {
        await updatePreferencesMutation.mutateAsync({
          notify_email: formData.notify_by_email,
        });
      } catch {
        // Ignore preference update errors, proceed with generation
      }
    }

    try {
      await generateMutation.mutateAsync({
        documentId,
        topicIds: selectedTopicIds,
        answers,
      });
      // Success - navigate to progress page
      router.replace(`/documents/${documentId}/progress`);
    } catch (error: unknown) {
      if (error instanceof ApiError && error.code === "quota_exceeded") {
        void quotaQuery.refetch();
        const query = new URLSearchParams(selectedTopicsQuery);
        query.set("error", "quota_exceeded");
        router.replace(`${topicsPath}?${query.toString()}`);
      } else {
        setSubmitError(error instanceof ApiError ? error.code : "unknown_error");
      }
    } finally {
      inFlightRef.current = false;
      setIsSubmitting(false);
    }
  }, [
    canSubmit,
    documentId,
    formData,
    generateMutation,
    meQuery.data,
    router,
    selectedTopicIds,
    quotaQuery,
    selectedTopicsQuery,
    topicsPath,
    updatePreferencesMutation,
  ]);

  // Loading state
  if (isLoading) {
    return (
      <PageShell title={t("title")}>
        <QuestionsSkeleton tCommon={tCommon} />
      </PageShell>
    );
  }

  // Error state for guard
  if (error) {
    return (
      <PageShell title={t("title")}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <p className={styles.errorMessage}>
              {tErrors("document_not_found")}
            </p>
            <ActionLink
              href="/materials"
              variant="secondary"
              className={styles.actionButton}
            >
              {tCommon("back")}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // If no topics selected, show warning and redirect option
  if (selectedTopicIds.length === 0) {
    return (
      <PageShell title={t("title")}>
        <Surface>
          <div className={styles.emptyState} role="alert">
            <p className={styles.emptyMessage}>{t("noTopicsSelected")}</p>
            <ActionLink
              href={topicsHref}
              variant="primary"
              onClick={handleBack}
            >
              {t("backToTopics")}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // Loading state for quota
  if (quotaQuery.isPending || planQuery.isLoading) {
    return (
      <PageShell title={t("title")}>
        <QuestionsSkeleton tCommon={tCommon} />
      </PageShell>
    );
  }

  // Error state for quota
  if (quotaQuery.isError) {
    return (
      <PageShell title={t("title")}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <p className={styles.errorMessage}>{tErrors("network_error")}</p>
            <button
              type="button"
              className={styles.retryButton}
              onClick={() => {
                void quotaQuery.refetch();
              }}
            >
              {tCommon("retry")}
            </button>
          </div>
        </Surface>
      </PageShell>
    );
  }

  if (guardRedirected) {
    return null;
  }

  // Show quota_exceeded error if coming from topics page
  const showQuotaError = searchParams.get("error") === "quota_exceeded";

  const plan = planQuery.data;

  return (
    <PageShell title={t("title")}>
      {showQuotaError && (
        <div className={styles.quotaErrorBanner} role="alert">
          {tErrors("quota_exceeded")}
        </div>
      )}

      <Surface title={t("levelLabel")}>
        <RadioGroup
          name="level"
          options={LEVELS}
          value={formData.level}
          onChange={(v) => {
            handleChange("level", v as Level);
          }}
          disabled={isSubmitting}
        />
      </Surface>

      <Surface title={t("depthLabel")}>
        <RadioGroup
          name="depth"
          options={DEPTHS}
          value={formData.depth}
          onChange={(v) => {
            handleChange("depth", v as Depth);
          }}
          disabled={isSubmitting}
        />
      </Surface>

      <Surface title={t("goalLabel")}>
        <RadioGroup
          name="goal"
          options={GOALS}
          value={formData.goal}
          onChange={(v) => {
            handleChange("goal", v as Goal);
          }}
          disabled={isSubmitting}
        />
      </Surface>

      <Surface title={t("notifyEmailLabel")}>
        <label className={styles.checkboxLabel}>
          <input
            type="checkbox"
            checked={formData.notify_by_email}
            onChange={(e) => {
              handleChange("notify_by_email", e.target.checked);
            }}
            disabled={isSubmitting}
            className={styles.checkbox}
          />
          <span className={styles.checkboxText}>{t("notifyEmailLabel")}</span>
        </label>
      </Surface>

      {/* Plan summary from server */}
      {(plan || quotaAvailable !== null) && (
        <div className={styles.quotaSummary}>
          <Surface>
            <div className={styles.quotaRow}>
              <span className={styles.quotaLabel}>{t("costLabel")}</span>
              <span
                className={`${styles.quotaValue} ${styles.cost} ${isOverQuota ? styles.overQuota : ""}`}
              >
                {planCost}
              </span>
            </div>
            <div className={styles.quotaRow}>
              <span className={styles.quotaLabel}>{t("remainingLabel")}</span>
              <span
                className={`${styles.quotaValue} ${isOverQuota ? styles.overQuota : ""}`}
              >
                {planAvailable !== null ? planAvailable : t("quotaUnknown")}
              </span>
            </div>
            {isOverQuota && (
              <div className={styles.quotaWarning} role="alert">
                {tErrors("quota_exceeded")}
              </div>
            )}
            {/* Plan parts preview */}
            {plan?.parts && plan.parts.length > 0 && (
              <div className={styles.planPartsPreview}>
                <div className={styles.planPartsTitle}>
                  {t("planPreviewTitle")}
                </div>
                <ul className={styles.planPartsList}>
                  {plan.parts.map((part) => (
                    <li key={part.index} className={styles.planPartItem}>
                      <span className={styles.planPartIndex}>
                        #{part.index}
                      </span>
                      <span className={styles.planPartTitle}>{part.title}</span>
                      <span className={styles.planPartTokens}>
                        {t("partTokens", { tokens: part.tokens })}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Surface>
        </div>
      )}

      {showQuotaError && (
        <div className={styles.quotaErrorBanner} role="alert">
          {tErrors("quota_exceeded")}
        </div>
      )}

      {submitError && (
        <div className={styles.errorSurface} role="alert">
          <Surface>
            <p className={styles.submitError}>{tErrors(submitError)}</p>
            {submitError === "document_not_ready" && (
              <ActionLink href={topicsHref} variant="secondary">
                {t("backToTopics")}
              </ActionLink>
            )}
          </Surface>
        </div>
      )}

      <div className={styles.pageActions}>
        <ActionLink
          href={topicsHref}
          variant="secondary"
          onClick={handleBack}
          disabled={isSubmitting}
        >
          {tCommon("back")}
        </ActionLink>
        <button
          type="button"
          className={`${styles.startButton} ${isSubmitting ? styles.submitting : ""} ${!canSubmit ? styles.disabled : ""}`}
          onClick={() => {
            void handleSubmit();
          }}
          disabled={!canSubmit || isSubmitting}
          aria-disabled={!canSubmit || isSubmitting}
        >
          {isSubmitting ? tCommon("loading") : t("startButton")}
        </button>
      </div>
    </PageShell>
  );
}

interface RadioGroupProps {
  name: string;
  options: { value: string; labelKey: string }[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

function RadioGroup({
  name,
  options,
  value,
  onChange,
  disabled,
}: RadioGroupProps) {
  const t = useTranslations("questions");

  return (
    <fieldset className={styles.radioGroup} disabled={disabled}>
      {options.map((option) => (
        <label key={option.value} className={styles.radioLabel}>
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => {
              onChange(option.value);
            }}
            disabled={disabled}
            className={styles.radio}
          />
          <span className={styles.radioText}>{t(option.labelKey)}</span>
        </label>
      ))}
    </fieldset>
  );
}

function QuestionsSkeleton({
  tCommon,
}: {
  tCommon: ReturnType<typeof import("next-intl").useTranslations>;
}) {
  return (
    <div
      className={styles.skeleton}
      role="status"
      aria-label={tCommon("loading")}
    >
      <Surface>
        <div className={styles.skeletonRadioGroup}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={styles.skeletonRadio} />
          ))}
        </div>
      </Surface>
      <Surface>
        <div className={styles.skeletonRadioGroup}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={styles.skeletonRadio} />
          ))}
        </div>
      </Surface>
      <Surface>
        <div className={styles.skeletonRadioGroup}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={styles.skeletonRadio} />
          ))}
        </div>
      </Surface>
      <Surface>
        <div className={styles.skeletonCheckbox} />
      </Surface>
    </div>
  );
}
