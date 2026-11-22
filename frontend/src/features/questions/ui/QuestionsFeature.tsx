'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useGenerateDocument } from '@/entities/document';
import { useQuota, QUOTA_QUERY_KEY } from '@/entities/user';
import { useDocumentStatusGuard } from '@/entities/document/guard/useDocumentStatusGuard';
import { ApiError } from '@/shared/api/errors';
import { ActionLink } from '@/shared/ui/action-link/ActionLink';
import { PageShell } from '@/shared/ui/page-shell/PageShell';
import { Surface } from '@/shared/ui/surface/Surface';
import { useQueryClient } from '@tanstack/react-query';
import type { GenerateRequest } from '@/entities/document';
import styles from './QuestionsFeature.module.css';

type Level = 'novice' | 'intermediate' | 'advanced';
type Depth = 'overview' | 'standard' | 'deep';
type Goal = 'refresh' | 'exam' | 'understand';

interface FormData {
  level: Level;
  depth: Depth;
  goal: Goal;
  notify_by_email: boolean;
}

const STORAGE_KEY_PREFIX = 'topics_';

const LEVELS: { value: Level; labelKey: string }[] = [
  { value: 'novice', labelKey: 'levelNovice' },
  { value: 'intermediate', labelKey: 'levelIntermediate' },
  { value: 'advanced', labelKey: 'levelAdvanced' },
];

const DEPTHS: { value: Depth; labelKey: string }[] = [
  { value: 'overview', labelKey: 'depthOverview' },
  { value: 'standard', labelKey: 'depthStandard' },
  { value: 'deep', labelKey: 'depthDeep' },
];

const GOALS: { value: Goal; labelKey: string }[] = [
  { value: 'refresh', labelKey: 'goalRefresh' },
  { value: 'exam', labelKey: 'goalExam' },
  { value: 'understand', labelKey: 'goalUnderstand' },
];

export function QuestionsFeature({ documentId }: { documentId: string }) {
  const t = useTranslations('questions');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');

  const router = useRouter();
  const searchParams = useSearchParams();
  const locale = searchParams.get('locale') || 'ru';
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState<FormData>({
    level: 'intermediate',
    depth: 'standard',
    goal: 'exam',
    notify_by_email: false,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([]);

  const generateMutation = useGenerateDocument();
  const quotaQuery = useQuota();

  // Centralized status guard - questions step allows 'parsed' status (new API)
  const { isLoading, error, hasRedirected: guardRedirected } = useDocumentStatusGuard({
    documentId,
    currentStep: 'questions',
  });

  // Read selected topic IDs from URL query params on mount
  useEffect(() => {
    const topicsParam = searchParams.get('topics');
    if (topicsParam) {
      try {
        const ids = topicsParam.split(',').filter(Boolean);
        if (ids.length > 0) {
          setSelectedTopicIds(ids);
        }
      } catch {
        // Invalid param, ignore
      }
    } else {
      // Fallback to sessionStorage for backward compatibility
      const stored = sessionStorage.getItem(`${STORAGE_KEY_PREFIX}${documentId}`);
      if (stored) {
        try {
          // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
          const parsed = JSON.parse(stored);
          const ids: unknown = parsed;
          if (Array.isArray(ids) && ids.every((id) => typeof id === 'string') && ids.length > 0) {
            setSelectedTopicIds(ids);
          }
        } catch {
          // Invalid JSON, ignore
        }
      }
    }
  }, [documentId, searchParams]);

  const quotaAvailable = quotaQuery.data?.available ?? null;
  const totalCost = selectedTopicIds.length; // Each topic costs 1 generation based on schema
  const isOverQuota = quotaAvailable !== null && totalCost > quotaAvailable;
  const canSubmit = !isSubmitting && !isOverQuota && selectedTopicIds.length > 0;

  const handleChange = useCallback(
    <K extends keyof FormData>(field: K, value: FormData[K]) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setSubmitError(null);
    },
    []
  );

  const handleBack = useCallback(() => {
    router.push(`/${locale}/documents/${documentId}/topics`);
  }, [router, locale, documentId]);

  const handleSubmit = useCallback(() => {
    if (!canSubmit) return;

    setIsSubmitting(true);
    setSubmitError(null);

    const body: GenerateRequest = {
      topic_ids: selectedTopicIds,
      answers: {
        level: formData.level,
        depth: formData.depth,
        goal: formData.goal,
      },
    };

    void generateMutation.mutateAsync({
      documentId,
      body,
    }).then(() => {
      // Clear sessionStorage on success
      sessionStorage.removeItem(`${STORAGE_KEY_PREFIX}${documentId}`);

      // Navigate to progress page
      router.push(`/${locale}/documents/${documentId}/progress`);
    }).catch((error: unknown) => {
      if (error instanceof ApiError) {
        const errorCode = error.code;
        setSubmitError(tErrors(errorCode));

        // Handle quota_exceeded (402) - invalidate quota cache and show back button
        if (errorCode === 'quota_exceeded') {
          void queryClient.invalidateQueries({ queryKey: QUOTA_QUERY_KEY });
        }
        // Handle document_not_ready (409) - user should go back to topics or refresh
        if (errorCode === 'document_not_ready') {
          // Error message will be shown via submitError, UI will have back button
        }
      } else {
        setSubmitError(tErrors('unknown_error'));
      }
    }).finally(() => {
      setIsSubmitting(false);
    });
  }, [canSubmit, documentId, formData, generateMutation, locale, queryClient, router, selectedTopicIds, tErrors]);

  // Loading state
  if (isLoading) {
    return (
      <PageShell title={t('title')}>
        <QuestionsSkeleton />
      </PageShell>
    );
  }

  // Error state for guard
  if (error) {
    return (
      <PageShell title={t('title')}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <p className={styles.errorMessage}>
              Не удалось загрузить документ. Возможно, он был удален или у вас нет доступа.
            </p>
            <ActionLink
              href={`/${locale}/materials`}
              variant="secondary"
              className={styles.actionButton}
            >
              {tCommon('back')}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // If no topics selected, show warning and redirect option
  if (selectedTopicIds.length === 0) {
    return (
      <PageShell title={t('title')}>
        <Surface>
          <div className={styles.emptyState} role="alert">
            <p className={styles.emptyMessage}>{t('noTopicsSelected')}</p>
            <ActionLink
              href={`/${locale}/documents/${documentId}/topics`}
              variant="primary"
              onClick={handleBack}
            >
              {t('backToTopics')}
            </ActionLink>
          </div>
        </Surface>
      </PageShell>
    );
  }

  // Loading state for quota
  if (quotaQuery.isPending) {
    return (
      <PageShell title={t('title')}>
        <QuestionsSkeleton />
      </PageShell>
    );
  }

  // Error state for quota
  if (quotaQuery.isError) {
    return (
      <PageShell title={t('title')}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <p className={styles.errorMessage}>{tErrors('network_error')}</p>
            <button type="button" className={styles.retryButton} onClick={() => { void quotaQuery.refetch(); }}>
              {tCommon('retry')}
            </button>
          </div>
        </Surface>
      </PageShell>
    );
  }

  if (guardRedirected) {
    return null;
  }

  return (
    <PageShell
      title={t('title')}
      actions={
        <div className={styles.pageActions}>
          <ActionLink
            href={`/${locale}/documents/${documentId}/topics`}
            variant="secondary"
            onClick={handleBack}
            disabled={isSubmitting}
          >
            {tCommon('back')}
          </ActionLink>
          <ActionLink
            href={`/${locale}/documents/${documentId}/progress`}
            variant="primary"
            onClick={handleSubmit}
            disabled={!canSubmit}
            aria-disabled={!canSubmit}
          >
            {isSubmitting ? tCommon('loading') : t('startButton')}
          </ActionLink>
        </div>
      }
    >
      <Surface title={t('levelLabel')}>
        <RadioGroup
          name="level"
          options={LEVELS}
          value={formData.level}
          onChange={(v) => { handleChange('level', v as Level); }}
          disabled={isSubmitting}
        />
      </Surface>

      <Surface title={t('depthLabel')}>
        <RadioGroup
          name="depth"
          options={DEPTHS}
          value={formData.depth}
          onChange={(v) => { handleChange('depth', v as Depth); }}
          disabled={isSubmitting}
        />
      </Surface>

      <Surface title={t('goalLabel')}>
        <RadioGroup
          name="goal"
          options={GOALS}
          value={formData.goal}
          onChange={(v) => { handleChange('goal', v as Goal); }}
          disabled={isSubmitting}
        />
      </Surface>

      <Surface title={t('notifyEmailLabel')}>
        <label className={styles.checkboxLabel}>
          <input
            type="checkbox"
            checked={formData.notify_by_email}
            onChange={(e) => { handleChange('notify_by_email', e.target.checked); }}
            disabled={isSubmitting}
            className={styles.checkbox}
          />
          <span className={styles.checkboxText}>{t('notifyEmailLabel')}</span>
        </label>
      </Surface>

      {quotaAvailable !== null && (
        <div className={styles.quotaSummary}>
          <Surface>
            <div className={styles.quotaRow}>
              <span className={styles.quotaLabel}>{t('costLabel')}</span>
              <span className={`${styles.quotaValue} ${styles.cost} ${isOverQuota ? styles.overQuota : ''}`}>
                {totalCost}
              </span>
            </div>
            <div className={styles.quotaRow}>
              <span className={styles.quotaLabel}>{t('remainingLabel')}</span>
              <span className={`${styles.quotaValue} ${isOverQuota ? styles.overQuota : ''}`}>
                {quotaAvailable}
              </span>
            </div>
            {isOverQuota && (
              <div className={styles.quotaWarning} role="alert">
                {tErrors('quota_exceeded')}
              </div>
            )}
          </Surface>
        </div>
      )}

      {submitError && (
        <div className={styles.errorSurface} role="alert">
          <Surface>
            <p className={styles.submitError}>{submitError}</p>
            {(submitError.includes('quota_exceeded') || submitError.includes('document_not_ready')) && (
              <ActionLink
                href={`/${locale}/documents/${documentId}/topics`}
                variant="secondary"
                className={styles.backToTopicsButton}
              >
                {t('backToTopics')}
              </ActionLink>
            )}
          </Surface>
        </div>
      )}
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

function RadioGroup({ name, options, value, onChange, disabled }: RadioGroupProps) {
  const t = useTranslations('questions');

  return (
    <fieldset className={styles.radioGroup} disabled={disabled}>
      {options.map((option) => (
        <label key={option.value} className={styles.radioLabel}>
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => { onChange(option.value); }}
            disabled={disabled}
            className={styles.radio}
          />
          <span className={styles.radioText}>{t(option.labelKey)}</span>
        </label>
      ))}
    </fieldset>
  );
}

function QuestionsSkeleton() {
  return (
    <div className={styles.skeleton} role="status" aria-label="Загрузка...">
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