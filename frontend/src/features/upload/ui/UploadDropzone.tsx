'use client';

import { useCallback, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';
import { ActionLink } from '@/shared/ui';
import { useUploadDocument } from '@/entities/document';
import { useRouter, useSearchParams } from 'next/navigation';
import { ApiError } from '@/shared/api/errors';
import styles from './UploadDropzone.module.css';

const ALLOWED_TYPES = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/markdown'];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

export function UploadDropzone() {
  const t = useTranslations('upload');
  const tErrors = useTranslations('errors');
  const tCommon = useTranslations('common');
  const router = useRouter();
  const searchParams = useSearchParams();
  const locale = searchParams.get('locale') || 'ru';
  const fileInputRef = useRef<HTMLInputElement>(null);
  const urlInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [googleDocUrl, setGoogleDocUrl] = useState('');
  const [fileError, setFileError] = useState<string | null>(null);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState<'file' | 'url'>('file');

  const uploadMutation = useUploadDocument();

  const validateFile = useCallback((file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      return tErrors('unsupported_file_type');
    }
    if (file.size > MAX_FILE_SIZE) {
      return tErrors('file_too_large');
    }
    return null;
  }, [tErrors]);

  const handleFileSelect = useCallback(
    (file: File | null) => {
      setFileError(null);
      if (!file) return;
      const error = validateFile(file);
      if (error) {
        setFileError(error);
        setSelectedFile(null);
      } else {
        setSelectedFile(file);
      }
    },
    [validateFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.currentTarget.classList.add(styles.dragOver);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.currentTarget.classList.remove(styles.dragOver);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.currentTarget.classList.remove(styles.dragOver);
      const file = e.dataTransfer.files[0];
      handleFileSelect(file);
    },
    [handleFileSelect]
  );

  const handleUrlChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setGoogleDocUrl(e.target.value);
    setUrlError(null);
  }, []);

  const handleFileInputClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      handleFileSelect(e.target.files?.[0] || null);
    },
    [handleFileSelect]
  );

  const handleSubmit = useCallback(async () => {
    if (activeTab === 'file') {
      if (!selectedFile) {
        setFileError(t('noFileSelected'));
        return;
      }
      setIsSubmitting(true);
      try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        const document = await uploadMutation.mutateAsync(formData);
        if (!document) throw new Error('Upload failed');
        router.push(`/${locale}/upload?doc=${document.id}`);
      } catch (error) {
        if (error instanceof ApiError) {
          setFileError(tErrors(error.code));
        } else {
          setFileError(tErrors('unknown_error'));
        }
      } finally {
        setIsSubmitting(false);
      }
    } else {
      if (!googleDocUrl.trim()) {
        setUrlError(t('noUrlEntered'));
        return;
      }
      setIsSubmitting(true);
      try {
        const formData = new FormData();
        formData.append('google_doc_url', googleDocUrl.trim());
        const document = await uploadMutation.mutateAsync(formData);
        if (!document) throw new Error('Import failed');
        router.push(`/${locale}/upload?doc=${document.id}`);
      } catch (error) {
        if (error instanceof ApiError) {
          setUrlError(tErrors(error.code));
        } else {
          setUrlError(tErrors('unknown_error'));
        }
      } finally {
        setIsSubmitting(false);
      }
    }
  }, [activeTab, selectedFile, googleDocUrl, uploadMutation, router, locale, t, tErrors]);

  const handleReset = useCallback(() => {
    setSelectedFile(null);
    setGoogleDocUrl('');
    setFileError(null);
    setUrlError(null);
    setIsSubmitting(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  return (
    <div className={styles.container}>
      <div className={styles.tabs} role="tablist" aria-label={t('title')}>
        <button
          role="tab"
          aria-selected={activeTab === 'file'}
          className={`${styles.tab} ${activeTab === 'file' ? styles.active : ''}`}
          onClick={() => { setActiveTab('file'); }}
        >
          {t('dropzoneTitle')}
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'url'}
          className={`${styles.tab} ${activeTab === 'url' ? styles.active : ''}`}
          onClick={() => { setActiveTab('url'); }}
        >
          {t('urlLabel')}
        </button>
      </div>

      {activeTab === 'file' && (
        <div className={styles.fileTab}>
          <div
            className={`${styles.dropzone} ${selectedFile ? styles.hasFile : ''} ${isSubmitting ? styles.submitting : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handleFileInputClick}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.md"
              onChange={handleFileInputChange}
              disabled={isSubmitting}
              className={styles.fileInput}
              aria-label={t('dropzoneTitle')}
            />
            {selectedFile ? (
              <div className={styles.fileInfo}>
                <span className={styles.fileName}>{selectedFile.name}</span>
                <span className={styles.fileSize}>
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </span>
                <button
                  type="button"
                  className={styles.removeFile}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleFileSelect(null);
                  }}
                  disabled={isSubmitting}
                  aria-label={t('replaceFileButton')}
                >
                  ×
                </button>
              </div>
            ) : (
              <>
                <p className={styles.dropzoneText}>{t('dropzoneTitle')}</p>
                <p className={styles.dropzoneHint}>{t('dropzoneHint')}</p>
              </>
            )}
          </div>
          {fileError && <p className={styles.error} role="alert">{fileError}</p>}
        </div>
      )}

      {activeTab === 'url' && (
        <div className={styles.urlTab}>
          <div className={styles.urlInputWrapper}>
            <input
              ref={urlInputRef}
              type="url"
              value={googleDocUrl}
              onChange={handleUrlChange}
              placeholder={t('urlPlaceholder')}
              disabled={isSubmitting}
              className={styles.urlInput}
              aria-label={t('urlLabel')}
            />
          </div>
          {urlError && <p className={styles.error} role="alert">{urlError}</p>}
        </div>
      )}

      <div className={styles.actions}>
        <ActionLink
          href={`/${locale}/materials`}
          variant="secondary"
          disabled={isSubmitting}
        >
          {tCommon('cancel')}
        </ActionLink>
        <button
          type="button"
          className={`${styles.submitButton} ${isSubmitting ? styles.submitting : ''}`}
          onClick={() => { void handleSubmit(); }}
          disabled={isSubmitting}
        >
          {isSubmitting ? tCommon('loading') : t('importButton')}
        </button>
      </div>

      {uploadMutation.isError && (
        <div className={styles.mutationError} role="alert">
          {uploadMutation.error instanceof ApiError
            ? tErrors(uploadMutation.error.code)
            : tErrors('unknown_error')}
          <button type="button" className={styles.retryButton} onClick={handleReset}>
            {tCommon('retry')}
          </button>
        </div>
      )}
    </div>
  );
}