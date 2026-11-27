"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ActionLink } from "@/shared/ui";
import { useUploadDocument, useImportGdocs } from "@/features/upload/api";
import { useRouter } from "@/shared/i18n/navigation-client";
import { ApiError } from "@/shared/api/errors";
import styles from "./UploadDropzone.module.css";

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".md"];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB
const GOOGLE_DOCS_URL_PATTERN =
  /^https:\/\/docs\.google\.com\/document\/d\/[a-zA-Z0-9-_]+/;

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes.toString()} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFileExtension(file: File): string | null {
  const name = file.name.toLowerCase();
  const hasValidExtension = ALLOWED_EXTENSIONS.some((ext) =>
    name.endsWith(ext)
  );
  if (!hasValidExtension) {
    return "unsupported_file_type";
  }
  if (file.size > MAX_FILE_SIZE) {
    return "file_too_large";
  }
  return null;
}

export function UploadDropzone() {
  const t = useTranslations("upload");
  const tErrors = useTranslations("errors");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const urlInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [googleDocUrl, setGoogleDocUrl] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState<"file" | "url">("file");

  const uploadMutation = useUploadDocument({
    onProgress: (percent) => {
      setUploadProgress(percent);
    },
  });
  const importGdocsMutation = useImportGdocs();

  const handleFileSelect = useCallback(
    (file: File | null) => {
      setFileError(null);
      if (!file) return;
      const errorCode = validateFileExtension(file);
      if (errorCode) {
        setFileError(tErrors(errorCode));
        setSelectedFile(null);
      } else {
        setSelectedFile(file);
      }
    },
    [tErrors]
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

  const handleUrlChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setGoogleDocUrl(e.target.value);
      setUrlError(null);
    },
    []
  );

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
    if (activeTab === "file") {
      if (!selectedFile) {
        setFileError(t("noFileSelected"));
        return;
      }
      setIsSubmitting(true);
      setUploadProgress(0);
      setFileError(null);
      try {
        const formData = new FormData();
        formData.append("file", selectedFile);
        const document = await uploadMutation.mutateAsync(formData);
        router.replace(`/upload?document=${document.id}`);
      } catch (error) {
        if (error instanceof ApiError) {
          setFileError(tErrors(error.code));
        } else {
          setFileError(tErrors("unknown_error"));
        }
      } finally {
        setIsSubmitting(false);
        setUploadProgress(null);
      }
    } else {
      const url = googleDocUrl.trim();
      if (!url) {
        setUrlError(t("noUrlEntered"));
        return;
      }
      if (!GOOGLE_DOCS_URL_PATTERN.test(url)) {
        setUrlError(tErrors("invalid_gdocs_url"));
        return;
      }
      setIsSubmitting(true);
      setUrlError(null);
      try {
        const document = await importGdocsMutation.mutateAsync(url);
        router.replace(`/upload?document=${document.id}`);
      } catch (error) {
        if (error instanceof ApiError) {
          setUrlError(tErrors(error.code));
        } else {
          setUrlError(tErrors("unknown_error"));
        }
      } finally {
        setIsSubmitting(false);
      }
    }
  }, [
    activeTab,
    selectedFile,
    googleDocUrl,
    uploadMutation,
    importGdocsMutation,
    router,
    t,
    tErrors,
  ]);

  return (
    <div className={styles.container}>
      <div className={styles.tabs} role="tablist" aria-label={t("title")}>
        <button
          role="tab"
          aria-selected={activeTab === "file"}
          className={`${styles.tab} ${activeTab === "file" ? styles.active : ""}`}
          onClick={() => {
            setActiveTab("file");
          }}
        >
          {t("dropzoneTitle")}
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "url"}
          className={`${styles.tab} ${activeTab === "url" ? styles.active : ""}`}
          onClick={() => {
            setActiveTab("url");
          }}
        >
          {t("urlLabel")}
        </button>
      </div>

      {activeTab === "file" && (
        <div className={styles.fileTab}>
          <div
            data-testid="dropzone-area"
            className={`${styles.dropzone} ${selectedFile ? styles.hasFile : ""} ${isSubmitting ? styles.submitting : ""}`}
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
              aria-label={t("dropzoneTitle")}
            />
            {selectedFile ? (
              <div className={styles.fileInfo}>
                <span className={styles.fileName}>{selectedFile.name}</span>
                <span className={styles.fileSize}>
                  {formatFileSize(selectedFile.size)}
                </span>
                <button
                  type="button"
                  className={styles.removeFile}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleFileSelect(null);
                  }}
                  disabled={isSubmitting}
                  aria-label={t("replaceFileButton")}
                >
                  ×
                </button>
              </div>
            ) : (
              <>
                <p className={styles.dropzoneText}>{t("dropzoneTitle")}</p>
                <p className={styles.dropzoneHint}>{t("dropzoneHint")}</p>
              </>
            )}
          </div>
          {uploadProgress !== null && (
            <div
              className={styles.progressWrapper}
              role="progressbar"
              aria-valuenow={uploadProgress}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={t("uploadProgress")}
            >
              <div className={styles.progressBar}>
                <div
                  className={styles.progressFill}
                  style={{ width: `${String(uploadProgress)}%` }}
                />
              </div>
              <span className={styles.progressText}>{uploadProgress}%</span>
            </div>
          )}
          {(fileError || uploadMutation.isError) && (
            <p className={styles.error} role="alert">
              {fileError ||
                (uploadMutation.error instanceof ApiError
                  ? tErrors(uploadMutation.error.code)
                  : tErrors("unknown_error"))}
            </p>
          )}
        </div>
      )}

      {activeTab === "url" && (
        <div className={styles.urlTab}>
          <div className={styles.urlInputWrapper}>
            <input
              ref={urlInputRef}
              type="url"
              value={googleDocUrl}
              onChange={handleUrlChange}
              placeholder={t("urlPlaceholder")}
              disabled={isSubmitting}
              className={styles.urlInput}
              aria-label={t("urlLabel")}
            />
          </div>
          {(urlError || importGdocsMutation.isError) && (
            <p className={styles.error} role="alert">
              {urlError ||
                (importGdocsMutation.error instanceof ApiError
                  ? tErrors(importGdocsMutation.error.code)
                  : tErrors("unknown_error"))}
            </p>
          )}
        </div>
      )}

      <div className={styles.actions}>
        <ActionLink
          href={`/materials`}
          variant="secondary"
          disabled={isSubmitting}
        >
          {tCommon("cancel")}
        </ActionLink>
        <button
          type="button"
          className={`${styles.submitButton} ${isSubmitting ? styles.submitting : ""}`}
          onClick={() => {
            void handleSubmit();
          }}
          disabled={isSubmitting}
        >
          {isSubmitting ? tCommon("loading") : t("importButton")}
        </button>
      </div>
    </div>
  );
}
