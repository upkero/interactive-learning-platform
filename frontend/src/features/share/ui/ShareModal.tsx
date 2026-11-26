'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';
import { useShareInfo, useShareDocument, useRevokeShare, useRevokePublicLink, type ShareUser } from '@/entities/share';
import { ApiError } from '@/shared/api/errors';
import styles from './ShareModal.module.css';

interface ShareModalProps {
  documentId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function ShareModal({ documentId, isOpen, onClose }: ShareModalProps) {
  const t = useTranslations('share');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors');

  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRevoking, setIsRevoking] = useState<string | null>(null);

  const shareQuery = useShareInfo(documentId);
  const shareMutation = useShareDocument();
  const revokeMutation = useRevokeShare();
  const revokePublicMutation = useRevokePublicLink();

  const shareInfo = shareQuery.data;
  const isPublic = shareInfo?.is_public ?? false;
  const sharedUsers = shareInfo?.shared_with ?? [];

  // Focus trap and escape handling
  const modalRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      previousActiveElement.current = document.activeElement as HTMLElement;
      document.body.style.overflow = 'hidden';
      // Focus the close button or first interactive element
      setTimeout(() => {
        const closeButton = modalRef.current?.querySelector('[data-close-button]') as HTMLElement | null;
        if (closeButton) {
          closeButton.focus();
        }
      }, 0);

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          onClose();
        }
      };
      document.addEventListener('keydown', handleKeyDown);
      return () => {
        document.removeEventListener('keydown', handleKeyDown);
        document.body.style.overflow = '';
        previousActiveElement.current?.focus();
      };
    }
  }, [isOpen, onClose]);

  const handleClose = useCallback(() => {
    setEmail('');
    setEmailError(null);
    setGeneralError(null);
    onClose();
  }, [onClose]);

  const handleOverlayClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  }, [handleClose]);

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleCloseWrapper = useCallback(() => {
    handleClose();
  }, [handleClose]);

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleOverlayClickWrapper = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  }, [handleClose]);

  const handleRevokePublic = useCallback(() => {
    setIsRevoking('public');
    setGeneralError(null);
    void revokePublicMutation.mutateAsync().then(() => {
      // Success
    }).catch((error: unknown) => {
      if (error instanceof ApiError) {
        setGeneralError(tErrors(error.code));
      } else {
        setGeneralError(tErrors('unknown_error'));
      }
    }).finally(() => {
      setIsRevoking(null);
    });
  }, [revokePublicMutation, tErrors]);

  const handleShareWithEmail = useCallback((e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setEmailError(null);
    setGeneralError(null);

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setEmailError(t('invalidEmail'));
      return;
    }

    setIsSubmitting(true);
    void shareMutation.mutateAsync({
      documentId,
      body: { email },
    }).then(() => {
      setEmail('');
    }).catch((error: unknown) => {
      if (error instanceof ApiError) {
        if (error.code === 'recipient_not_registered') {
          setEmailError(t('userNotFound'));
        } else if (error.code === 'share_with_self') {
          setEmailError(t('shareSelfForbidden'));
        } else {
          setGeneralError(tErrors(error.code));
        }
      } else {
        setGeneralError(tErrors('unknown_error'));
      }
    }).finally(() => {
      setIsSubmitting(false);
    });
  }, [documentId, email, shareMutation, t, tErrors]);

  const handleRevokeUser = useCallback((userId: string) => {
    setIsRevoking(userId);
    setGeneralError(null);
    void revokeMutation.mutateAsync().then(() => {
      // Success
    }).catch((error: unknown) => {
      if (error instanceof ApiError) {
        setGeneralError(tErrors(error.code));
      } else {
        setGeneralError(tErrors('unknown_error'));
      }
    }).finally(() => {
      setIsRevoking(null);
    });
  }, [revokeMutation, tErrors]);

  // Wrapper functions for async handlers used in JSX event handlers
  const onRevokePublicClick = useCallback(() => {
    handleRevokePublic();
  }, [handleRevokePublic]);

  const onRevokeUserClick = useCallback((userId: string) => {
    handleRevokeUser(userId);
  }, [handleRevokeUser]);

  if (!isOpen) return null;

  return (
    <div
      className={styles.overlay}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="share-modal-title"
    >
      <div
        ref={modalRef}
        className={styles.modal}
        onClick={(e) => { e.stopPropagation(); }}
      >
        <header className={styles.header}>
          <h2 id="share-modal-title" className={styles.title}>{t('title')}</h2>
          <button
            type="button"
            className={styles.closeButton}
            onClick={handleClose}
            data-close-button
            aria-label={tCommon('close')}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        {generalError && (
          <div className={styles.errorBanner} role="alert">
            {generalError}
          </div>
        )}

        <div className={styles.content}>
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>{t('publicLinkTitle')}</h3>
            <p className={styles.sectionDescription}>{t('publicLinkDescription')}</p>

            <div className={styles.urlBlock}>
              <p className={styles.noLinkText}>{t('noPublicLink')}</p>
              <p className={styles.hintText}>{t('publicLinkNotSupported')}</p>
            </div>
          </section>

          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>{t('inviteByEmailTitle')}</h3>
            <p className={styles.sectionDescription}>{t('inviteByEmailDescription')}</p>
            <form onSubmit={handleShareWithEmail} className={styles.inviteForm}>
              <div className={styles.inputGroup}>
                <label htmlFor="share-email" className={styles.visuallyHidden}>
                  {t('emailLabel')}
                </label>
                <input
                  type="email"
                  id="share-email"
                  className={`${styles.emailInput} ${emailError ? styles.error : ''}`}
                  placeholder={t('emailPlaceholder')}
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (emailError) setEmailError(null);
                  }}
                  disabled={isSubmitting}
                  aria-describedby={emailError ? 'email-error' : undefined}
                  aria-invalid={!!emailError}
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
                disabled={isSubmitting || !email.trim()}
              >
                {isSubmitting ? tCommon('loading') : t('grantButton')}
              </button>
            </form>
          </section>

          {(sharedUsers.length > 0 || isPublic) && (
            <section className={styles.section}>
              <h3 className={styles.sectionTitle}>{t('sharedWithTitle')}</h3>
              <ul className={styles.sharedList} role="list">
                {isPublic && (
                  <li className={styles.sharedItem}>
                    <div className={styles.sharedUserInfo}>
                      <span className={styles.sharedUserAvatar}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M18 13.5C18 16.5379 15.5379 19 12 19C8.46215 19 6 16.5379 6 13.5C6 10.4621 8.46215 8 12 8C15.5379 8 18 10.4621 18 13.5Z" />
                          <path d="M12 2C8.13401 2 5 5.13401 5 9C5 12.866 8.13401 16 12 16C15.866 16 19 12.866 19 9C19 5.13401 15.866 2 12 2Z" />
                        </svg>
                      </span>
                      <span className={styles.sharedUserName}>{t('publicAccess')}</span>
                    </div>
                    <button
                      type="button"
                      className={styles.revokeButton}
                      onClick={onRevokePublicClick}
                      disabled={isRevoking === 'public'}
                      aria-label={t('revokePublicLink')}
                    >
                      {isRevoking === 'public' ? (
                        <span className={styles.spinner} />
                      ) : (
                        t('revokeButton')
                      )}
                    </button>
                  </li>
                )}
                {sharedUsers.map((user: ShareUser) => (
                  <li key={user.id} className={styles.sharedItem}>
                    <div className={styles.sharedUserInfo}>
                      <span className={styles.sharedUserAvatar}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                          <circle cx="12" cy="7" r="4" />
                        </svg>
                      </span>
                      <div className={styles.sharedUserDetails}>
                        <span className={styles.sharedUserName}>{user.name || user.email}</span>
                        <span className={styles.sharedUserEmail}>{user.email}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className={styles.revokeButton}
                      onClick={() => { onRevokeUserClick(user.id); }}
                      disabled={isRevoking === user.id}
                      aria-label={`${t('revokeButton')} ${user.email}`}
                    >
                      {isRevoking === user.id ? (
                        <span className={styles.spinner} />
                      ) : (
                        t('revokeButton')
                      )}
                    </button>
                  </li>
                ))}
                {(sharedUsers.length === 0 && !isPublic) && (
                  <li className={styles.emptyShared}>
                    <p>{t('sharedWithNone')}</p>
                  </li>
                )}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}