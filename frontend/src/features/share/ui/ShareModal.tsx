"use client";

import { useEffect, useRef, useState, type SyntheticEvent } from "react";
import { useTranslations } from "next-intl";
import { useDocument } from "@/entities/document";
import { useShareDocument } from "@/entities/share";
import { ApiError } from "@/shared/api/errors";
import styles from "./ShareModal.module.css";

interface ShareModalProps {
  documentId: string;
  onClose: () => void;
}

export function ShareModal({ documentId, onClose }: ShareModalProps) {
  const t = useTranslations("share");
  const tCommon = useTranslations("common");
  const tEmpty = useTranslations("empty");
  const tErrors = useTranslations("errors");
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const documentQuery = useDocument(documentId);
  const share = useShareDocument();
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus();

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement) previousFocus.focus();
    };
  }, [onClose]);

  const handleSubmit = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    const recipient = email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient)) {
      setEmailError(t("invalidEmail"));
      return;
    }

    setEmailError(null);
    share.mutate(
      { document_id: documentId, email: recipient },
      {
        onSuccess: () => {
          setEmail("");
        },
      }
    );
  };

  const documentError = documentQuery.error;
  const canShare = documentQuery.data?.role === "owner";
  const sharedUsers = documentQuery.data?.shared_with ?? [];
  const shareError = share.error;
  const shareCode =
    shareError instanceof ApiError ? shareError.code : "unknown_error";
  const recipientError =
    shareCode === "recipient_not_registered"
      ? t("userNotFound")
      : shareCode === "share_with_self"
        ? t("shareSelfForbidden")
        : null;
  const inputError = emailError ?? recipientError;

  return (
    <div
      className={styles.overlay}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="share-modal-title"
    >
      <div className={styles.modal}>
        <header className={styles.header}>
          <h2 id="share-modal-title" className={styles.title}>
            {t("title")}
          </h2>
          <button
            type="button"
            ref={closeButton}
            className={styles.closeButton}
            onClick={onClose}
            aria-label={tCommon("close")}
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        <div className={styles.content}>
          {documentQuery.isPending && <p role="status">{tCommon("loading")}</p>}
          {documentQuery.isError && (
            <p className={styles.errorBanner} role="alert">
              {tErrors(
                documentError instanceof ApiError
                  ? documentError.code
                  : "unknown_error"
              )}
            </p>
          )}
          {documentQuery.isSuccess && !canShare && (
            <p className={styles.errorBanner} role="alert">
              {tErrors("document_not_found")}
            </p>
          )}
          {documentQuery.isSuccess && canShare && (
            <>
              {shareError && !recipientError && (
                <p className={styles.errorBanner} role="alert">
                  {tErrors(shareCode)}
                </p>
              )}
              <section className={styles.section}>
                <h3 className={styles.sectionTitle}>
                  {t("inviteByEmailTitle")}
                </h3>
                <p className={styles.sectionDescription}>
                  {t("inviteByEmailDescription")}
                </p>
                <form onSubmit={handleSubmit} className={styles.inviteForm}>
                  <div className={styles.inputGroup}>
                    <label
                      htmlFor="share-email"
                      className={styles.visuallyHidden}
                    >
                      {t("emailLabel")}
                    </label>
                    <input
                      type="email"
                      id="share-email"
                      className={`${styles.emailInput} ${inputError ? styles.error : ""}`}
                      placeholder={t("emailPlaceholder")}
                      value={email}
                      onChange={(event) => {
                        setEmail(event.target.value);
                        setEmailError(null);
                        if (share.isError) share.reset();
                      }}
                      disabled={share.isPending}
                      aria-describedby={
                        inputError ? "share-email-error" : undefined
                      }
                      aria-invalid={!!inputError}
                    />
                    {inputError && (
                      <p
                        id="share-email-error"
                        className={styles.inputError}
                        role="alert"
                      >
                        {inputError}
                      </p>
                    )}
                  </div>
                  <button
                    type="submit"
                    className={`${styles.actionButton} ${styles.primary}`}
                    disabled={share.isPending || !email.trim()}
                  >
                    {share.isPending ? tCommon("loading") : t("grantButton")}
                  </button>
                </form>
              </section>

              <section className={styles.section}>
                <h3 className={styles.sectionTitle}>{t("sharedWithTitle")}</h3>
                {sharedUsers.length ? (
                  <ul className={styles.sharedList} role="list">
                    {sharedUsers.map((user) => (
                      <li key={user.email} className={styles.sharedItem}>
                        <div className={styles.sharedUserDetails}>
                          {user.display_name && (
                            <span className={styles.sharedUserName}>
                              {user.display_name}
                            </span>
                          )}
                          <span className={styles.sharedUserEmail}>
                            {user.email}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className={styles.sectionDescription}>
                    {tEmpty("sharedWithNone")}
                  </p>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
