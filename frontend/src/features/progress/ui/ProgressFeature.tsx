'use client';

import { useCallback, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEventStream, type SseEventMessage } from '@/shared/lib/sse/useEventStream';
import { useDocumentStatusGuard } from '@/entities/document/guard/useDocumentStatusGuard';
import { ActionLink } from '@/shared/ui/action-link/ActionLink';
import { PageShell } from '@/shared/ui/page-shell/PageShell';
import { Surface } from '@/shared/ui/surface/Surface';
import styles from './ProgressFeature.module.css';

interface StageEventData {
  stage: string;
  progress?: number;
  message?: string;
  document_id: string;
}

interface PartStatusEventData {
  part_id: string;
  part_index: number;
  title: string;
  status: 'queued' | 'generating' | 'ready' | 'failed';
  error_code?: string;
}

interface KeyTermEventData {
  term: string;
  definition: string;
}

interface DocumentDoneEventData {
  document_id: string;
  status: 'ready';
}

interface FatalErrorEventData {
  error_code: string;
  message: string;
}

type SseEventData = StageEventData | PartStatusEventData | KeyTermEventData | DocumentDoneEventData | FatalErrorEventData;

interface PartInfo {
  id: string;
  index: number;
  title: string;
  status: 'queued' | 'generating' | 'ready' | 'failed';
  errorCode?: string;
}

export function ProgressFeature({ documentId }: { documentId: string }) {
  const t = useTranslations('progress');
  const tErrors = useTranslations('errors');
  const tCommon = useTranslations('common');
  const tUpload = useTranslations('upload');

  const router = useRouter();
  const searchParams = useSearchParams();
  const locale = searchParams.get('locale') || 'ru';

  const [stages, setStages] = useState<string[]>([]);
  const [parts, setParts] = useState<PartInfo[]>([]);
  const [keyTerms, setKeyTerms] = useState<{ term: string; definition: string }[]>([]);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [hasRedirected, setHasRedirected] = useState(false);

  const partStartTimes = useRef<Map<string, number>>(new Map());
  const firstPartCompletedTime = useRef<number | null>(null);
  const partDurations = useRef<number[]>([]);

  // Centralized status guard - progress step allows 'generating' status
  const { isLoading, error, hasRedirected: guardRedirected } = useDocumentStatusGuard({
    documentId,
    currentStep: 'progress',
  });

  const handleEvent = useCallback((message: SseEventMessage<SseEventData>) => {
    if (hasRedirected || guardRedirected) return;

    const { event, data } = message;

    switch (event) {
      case 'stage': {
        const stageData = data as StageEventData;
        if (stageData.stage) {
          setStages((prev) => [...prev, stageData.stage]);
        }
        break;
      }
      case 'part_status': {
        const partData = data as PartStatusEventData;
        setParts((prev) => {
          const existingIndex = prev.findIndex((p) => p.id === partData.part_id);
          const newPart: PartInfo = {
            id: partData.part_id,
            index: partData.part_index,
            title: partData.title,
            status: partData.status,
            errorCode: partData.error_code,
          };

          // Track part start/completion times for ETA calculation
          if (partData.status === 'generating' && !partStartTimes.current.has(partData.part_id)) {
            partStartTimes.current.set(partData.part_id, Date.now());
          } else if ((partData.status === 'ready' || partData.status === 'failed') && partStartTimes.current.has(partData.part_id)) {
            const startTime = partStartTimes.current.get(partData.part_id) as number;
            const duration = (Date.now() - startTime) / 1000;
            partDurations.current.push(duration);
            partStartTimes.current.delete(partData.part_id);

            if (firstPartCompletedTime.current === null) {
              firstPartCompletedTime.current = Date.now();
            }
          }

          if (existingIndex >= 0) {
            const updated = [...prev];
            updated[existingIndex] = newPart;
            return updated;
          }
          return [...prev, newPart].sort((a, b) => a.index - b.index);
        });
        break;
      }
      case 'key_term': {
        const termData = data as KeyTermEventData;
        setKeyTerms((prev) => [...prev, { term: termData.term, definition: termData.definition }]);
        break;
      }
      case 'document_done': {
        // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
        if (!hasRedirected && !guardRedirected) {
          setHasRedirected(true);
          router.push(`/${locale}/documents/${documentId}`);
        }
        break;
      }
      case 'fatal_error': {
        const errorData = data as FatalErrorEventData;
        // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
        if (!hasRedirected && !guardRedirected) {
          setErrorCode(errorData.error_code || 'generation_conflict');
        }
        break;
      }
    }
  }, [hasRedirected, guardRedirected, router, locale, documentId]);

  const sseUrl = `/api/v1/documents/${documentId}/events`;

  const { status: sseStatus } = useEventStream<SseEventData>({
    url: sseUrl,
    enabled: !hasRedirected && !errorCode && !guardRedirected,
    terminalEvents: ['document_done', 'fatal_error'],
    onEvent: handleEvent,
  });

  // Calculate ETA
  const eta = useMemo(() => {
    const totalParts = parts.length;
    const doneParts = parts.filter((p) => p.status === 'ready' || p.status === 'failed').length;
    const currentPart = parts.find((p) => p.status === 'generating');

    if (totalParts === 0) return 5;

    const T_AVG_BASE = 25; // seconds
    let T_avg = T_AVG_BASE;

    if (partDurations.current.length > 0) {
      const sum = partDurations.current.reduce((a, b) => a + b, 0);
      T_avg = sum / partDurations.current.length;
    }

    const remainingParts = totalParts - doneParts;
    let t_elapsed_current = 0;

    if (currentPart && partStartTimes.current.has(currentPart.id)) {
      const startTime = partStartTimes.current.get(currentPart.id) as number;
      t_elapsed_current = (Date.now() - startTime) / 1000;
      t_elapsed_current = Math.min(t_elapsed_current, 0.8 * T_avg);
    }

    const etaSeconds = Math.max(5, Math.ceil(remainingParts * T_avg - t_elapsed_current));
    return etaSeconds;
  }, [parts]);

  // Loading state
  if (isLoading) {
    return (
      <PageShell title={t('title')} description={t('etaRemaining', { seconds: 0 })}>
        <ProgressSkeleton />
      </PageShell>
    );
  }

  // Error state
  if (error) {
    return (
      <PageShell title={t('title')}>
        <Surface>
          <div className={styles.errorState} role="alert">
            <h2 className={styles.errorTitle}>{tUpload('parsingFailed')}</h2>
            <p className={styles.errorMessage}>
              Не удалось загрузить документ. Возможно, он был удален или у вас нет доступа.
            </p>
            <div className={styles.errorActions}>
              <button
                type="button"
                className={`${styles.actionButton} ${styles.primary}`}
                onClick={() => {
                  setErrorCode(null);
                  setHasRedirected(false);
                }}
              >
                {t('retryButton')}
              </button>
              <ActionLink
                href={`/${locale}/materials`}
                variant="secondary"
                className={styles.actionButton}
              >
                {tCommon('back')}
              </ActionLink>
            </div>
          </div>
        </Surface>
      </PageShell>
    );
  }

  if (guardRedirected) {
    return null;
  }

  const sortedParts = useMemo(
    () => [...parts].sort((a, b) => a.index - b.index),
    [parts]
  );

  return (
    <PageShell
      title={t('title')}
      description={t('etaRemaining', { seconds: eta })}
    >
      {sseStatus === 'reconnecting' && (
        <div className={styles.reconnectBanner} role="status">
          {t('connectionLost')}
        </div>
      )}

      <Surface title={t('stageLogTitle')}>
        <div className={styles.stageLog}>
          {stages.length === 0 ? (
            <p className={styles.emptyStage}>{t('waitingForStages')}</p>
          ) : (
            <ul className={styles.stageList} role="list">
              {stages.map((stage, index) => (
                <li key={index} className={styles.stageItem}>
                  <span className={styles.stageBullet} />
                  <span className={styles.stageText}>{stage}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Surface>

      <Surface title={t('partsTitle')}>
        <div className={styles.partsList} role="list">
          {sortedParts.length === 0 ? (
            <p className={styles.emptyParts}>{t('waitingForParts')}</p>
          ) : (
            sortedParts.map((part) => (
              <PartCard key={part.id} part={part} t={t} tErrors={tErrors} />
            ))
          )}
        </div>
      </Surface>

      <Surface title={t('keyTermsTitle')} muted>
        <div className={styles.keyTerms}>
          {keyTerms.length === 0 ? (
            <p className={styles.emptyKeyTerms}>{t('noKeyTermsYet')}</p>
          ) : (
            <dl className={styles.keyTermsList}>
              {keyTerms.map((kt, index) => (
                <div key={index} className={styles.keyTermItem}>
                  <dt className={styles.keyTermName}>{kt.term}</dt>
                  <dd className={styles.keyTermDef}>{kt.definition}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </Surface>

      <div className={styles.actions}>
        <ActionLink
          href={`/${locale}/materials`}
          variant="secondary"
        >
          {t('backToMaterials')}
        </ActionLink>
      </div>
    </PageShell>
  );
}

interface PartCardProps {
  part: PartInfo;
  t: ReturnType<typeof useTranslations>;
  tErrors: ReturnType<typeof useTranslations>;
}

function PartCard({ part, t, tErrors }: PartCardProps) {
  const statusConfig = {
    queued: { label: t('partStatus.queued'), className: styles.statusQueued },
    generating: { label: t('partStatus.generating'), className: styles.statusGenerating },
    ready: { label: t('partStatus.ready'), className: styles.statusReady },
    failed: { label: t('partStatus.failed'), className: styles.statusFailed },
  }[part.status];

  return (
    <article className={`${styles.partCard} ${styles[part.status]}`} role="listitem">
      <header className={styles.partHeader}>
        <h3 className={styles.partTitle}>{part.title}</h3>
        <span className={`${styles.partStatus} ${statusConfig.className}`}>
          {statusConfig.label}
        </span>
      </header>
      {part.status === 'generating' && (
        <div className={styles.partProgress} role="progressbar" aria-valuenow={0} aria-valuemin={0} aria-valuemax={100}>
          <div className={styles.partProgressFill} />
        </div>
      )}
      {part.status === 'failed' && part.errorCode && (
        <div className={styles.partError} role="alert">
          <p className={styles.partErrorText}>
            {tErrors(part.errorCode as keyof typeof tErrors)}
          </p>
          <p className={styles.partErrorHint}>{t('partFailedHint')}</p>
          <button
            type="button"
            className={styles.retryPartButton}
            onClick={() => {
              // TODO: Implement retry part API call
            }}
          >
            {t('retryPartButton')}
          </button>
        </div>
      )}
    </article>
  );
}

function ProgressSkeleton() {
  return (
    <div className={styles.skeleton} role="status" aria-label="Загрузка...">
      <Surface>
        <div className={styles.skeletonStageLog}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={styles.skeletonStageItem} />
          ))}
        </div>
      </Surface>
      <Surface>
        <div className={styles.skeletonParts}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={styles.skeletonPartItem} />
          ))}
        </div>
      </Surface>
      <Surface>
        <div className={styles.skeletonKeyTerms} />
      </Surface>
    </div>
  );
}