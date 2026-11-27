"use client";

import { useEffect, useRef, useCallback } from "react";
import styles from "./Dialog.module.css";

export interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  triggerRef?: React.RefObject<HTMLElement | null>;
  size?: "sm" | "md" | "lg";
  closeOnOverlayClick?: boolean;
  closeOnEscape?: boolean;
}

export function Dialog({
  isOpen,
  onClose,
  title,
  children,
  triggerRef,
  size = "md",
  closeOnOverlayClick = true,
  closeOnEscape = true,
}: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);
  const titleId = useRef(
    `dialog-title-${Math.random().toString(36).slice(2)}`
  ).current;

  const handleClose = useCallback(() => {
    onClose();
  }, [onClose]);

  const handleOverlayClick = useCallback(
    (e: MouseEvent) => {
      if (!closeOnOverlayClick) return;
      const dialog = dialogRef.current;
      if (dialog && e.target === dialog) {
        const rect = dialog.getBoundingClientRect();
        const isInDialog =
          e.clientX >= rect.left &&
          e.clientX <= rect.right &&
          e.clientY >= rect.top &&
          e.clientY <= rect.bottom;
        if (!isInDialog) {
          handleClose();
        }
      }
    },
    [closeOnOverlayClick, handleClose]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!closeOnEscape) return;
      if (e.key === "Escape") {
        handleClose();
      }
    },
    [closeOnEscape, handleClose]
  );

  // Handle Escape key globally when dialog is open
  useEffect(() => {
    if (!isOpen || !closeOnEscape) return;
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, closeOnEscape, handleKeyDown]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (isOpen) {
      previousActiveElement.current =
        document.activeElement as HTMLElement | null;
      dialog.showModal();
      dialog.addEventListener("click", handleOverlayClick);
    } else {
      dialog.close();
      dialog.removeEventListener("click", handleOverlayClick);
      previousActiveElement.current?.focus();
    }

    return () => {
      dialog.removeEventListener("click", handleOverlayClick);
      if (dialog.open) {
        dialog.close();
      }
    };
  }, [isOpen, handleOverlayClick, triggerRef]);

  if (!isOpen) return null;

  return (
    <dialog
      ref={dialogRef}
      className={`${styles.dialog} ${styles[size]}`}
      aria-modal="true"
      aria-labelledby={titleId}
      onClose={handleClose}
    >
      <div className={styles.backdrop} />
      <div className={styles.content}>
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          <button
            type="button"
            className={styles.closeButton}
            onClick={handleClose}
            aria-label="Close"
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>
        <div className={styles.body}>{children}</div>
      </div>
    </dialog>
  );
}

export interface DialogTriggerProps {
  children: React.ReactElement;
  onOpen: () => void;
}

export function DialogTrigger({ children, onOpen }: DialogTriggerProps) {
  if (!React.isValidElement(children)) {
    throw new Error("DialogTrigger expects a single React element as child");
  }
  return React.cloneElement(
    children as React.ReactElement<Record<string, unknown>>,
    {
      onClick: (e: React.MouseEvent<HTMLElement>) => {
        e.stopPropagation();
        onOpen();
      },
    }
  );
}

import React from "react";
