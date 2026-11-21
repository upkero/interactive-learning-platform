'use client';

import { Suspense } from 'react';
import { useTranslations } from 'next-intl';
import { useSearchParams } from 'next/navigation';
import { PageShell, ActionLink } from '@/shared/ui';
import { UploadFeature } from '@/features/upload';

function UploadContent() {
  const t = useTranslations('upload');
  const tCommon = useTranslations('common');
  const searchParams = useSearchParams();
  const locale = searchParams.get('locale') || 'ru';

  return (
    <PageShell
      title={t('title')}
      actions={
        <ActionLink href={`/${locale}/materials`} variant="secondary">
          {tCommon('back')}
        </ActionLink>
      }
    >
      <Suspense fallback={<div className="loading" aria-live="polite">{tCommon('loading')}</div>}>
        <UploadFeature />
      </Suspense>
    </PageShell>
  );
}

export default function UploadPage() {
  return <UploadContent />;
}