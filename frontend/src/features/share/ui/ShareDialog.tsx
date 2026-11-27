"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { useDocument } from "@/entities/document";
import { useShareMaterial, type SharedWithOut } from "../api";
import { Dialog } from "@/shared/ui";
import { isApiError } from "@/shared/api/errors";
import styles from "./ShareDialog.module.css";

interface ShareDialogProps {
  documentId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function ShareDialog({ documentId, isOpen, onClose }: ShareDialogProps) {
  const t = useTranslations("share");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");

  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);

  const documentQuery = useDocument(documentId, { enabled: isOpen });
  const shareMutation = useShareMaterial();

  const document = documentQuery.data;
  const isOwner = document?.role === "owner";
  const sharedUsers =
    document && isOwner && document.shared_with ? document.shared_with : [];

  const handleClose = useCallback(() => {
    setEmail("");
    setEmailError(null);
    onClose();
  }, [onClose]);

  const getErrorMessage = useCallback(
    (error: unknown): string => {
      if (isApiError(error)) {
        return tErrors(error.code);
      }
      if (error instanceof TypeError && error.message.includes("fetch")) {
        return tErrors("network_error");
      }
      if (error instanceof Error) {
        return tErrors("unknown_error");
      }
      return tErrors("unknown_error");
    },
    [tErrors]
  );

  const handleShare = useCallback(
    async (e: React.SubmitEvent<HTMLFormElement>) => {
      e.preventDefault();
      setEmailError(null);

      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        setEmailError(t("invalidEmail"));
        return;
      }

      try {
        await shareMutation.mutateAsync({ documentId, email });
        setEmail("");
      } catch (error) {
        const message = getErrorMessage(error);
        if (isApiError(error)) {
          if (
            error.code === "recipient_not_registered" ||
            error.code === "share_with_self"
          ) {
            setEmailError(message);
          } else {
            setEmailError(message);
          }
        } else {
          setEmailError(message);
        }
      }
    },
    [documentId, email, shareMutation, t, getErrorMessage]
  );

  if (!isOpen) return null;
  if (!isOwner) {
    return (
      <Dialog
        isOpen={isOpen}
        onClose={handleClose}
        title={t("title")}
        size="md"
      >
        <div className={styles.notOwner}>
          <p>{tCommon("loading")}</p>
        </div>
      </Dialog>
    );
  }

  // At this point, document is guaranteed to be non-null and isOwner is true
  const docTitle = document.title;
  const docPartsCount = document.parts.length;

  return (
    <Dialog isOpen={isOpen} onClose={handleClose} title={t("title")} size="md">
      <div className={styles.container}>
        <div className={styles.documentInfo}>
          <h3 className={styles.documentTitle}>{docTitle}</h3>
          <p className={styles.partsCount}>
            {t("partsCount", { count: docPartsCount })}
          </p>
        </div>

        <p className={styles.warning} role="note">
          {t("recipientNote")}
        </p>

        <form
          onSubmit={(e) => {
            void handleShare(e);
          }}
          className={styles.form}
        >
          <div className={styles.inputGroup}>
            <label htmlFor="share-email" className={styles.label}>
              {t("emailLabel")}
            </label>
            <input
              type="email"
              id="share-email"
              className={`${styles.emailInput} ${emailError ? styles.error : ""}`}
              placeholder={t("emailPlaceholder")}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (emailError) setEmailError(null);
              }}
              disabled={shareMutation.isPending}
              aria-describedby={emailError ? "email-error" : undefined}
              aria-invalid={!!emailError}
              autoFocus
            />
            {emailError && (
              <p id="email-error" className={styles.inputError} role="alert">
                {emailError}
              </p>
            )}
          </div>
          <button
            type="submit"
            className={`${styles.actionButton} ${styles.primary}`}
            disabled={shareMutation.isPending || !email.trim()}
          >
            {shareMutation.isPending ? tCommon("loading") : t("grantButton")}
          </button>
        </form>

        <section
          className={styles.sharedSection}
          aria-labelledby="shared-with-heading"
        >
          <h3 id="shared-with-heading" className={styles.sectionTitle}>
            {t("sharedWithTitle")}
          </h3>
          {sharedUsers.length > 0 ? (
            <ul className={styles.sharedList} role="list">
              {sharedUsers.map((user: SharedWithOut) => (
                <li key={user.email} className={styles.sharedItem}>
                  <div className={styles.sharedUserInfo}>
                    <span className={styles.sharedUserAvatar}>
                      <svg
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                      </svg>
                    </span>
                    <div className={styles.sharedUserDetails}>
                      <span className={styles.sharedUserName}>
                        {user.display_name ?? user.email}
                      </span>
                      <span className={styles.sharedUserEmail}>
                        {user.email}
                      </span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.emptyShared}>{t("sharedWithNone")}</p>
          )}
        </section>
      </div>
    </Dialog>
  );
}
