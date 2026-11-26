"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "@/shared/i18n/navigation-client";
import { type SyntheticEvent, useState } from "react";
import { useLogin, useRegister } from "../api";
import { sanitizeNextUrl } from "../model/sanitizeNext";
import { authCredentialsSchema, registerSchema } from "../model/schemas";
import { useApiErrorMessage } from "@/shared/api";
import styles from "./LoginForm.module.css";

export function LoginForm({ mode = "login" }: { mode?: "login" | "register" }) {
  const t = useTranslations("auth");
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const loginMutation = useLogin();
  const registerMutation = useRegister();

  const mutation = mode === "login" ? loginMutation : registerMutation;

  const handleSubmit = (e: SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormError(null);

    const schema = mode === "login" ? authCredentialsSchema : registerSchema;
    const parsed = schema.safeParse(
      mode === "login"
        ? { email, password }
        : { email, password, display_name: displayName || undefined }
    );

    if (!parsed.success) {
      const issue = parsed.error.errors[0]?.message;
      setFormError(issue ? t(issue) : t("validation_error"));
      return;
    }

    mutation.mutate(parsed.data);
  };

  if (mutation.isError) {
    setFormError(useApiErrorMessage(mutation.error));
  }

  return (
    <form onSubmit={handleSubmit} className={styles.form} noValidate>
      <h1 className={styles.title}>
        {mode === "login" ? t("loginTitle") : t("registerTitle")}
      </h1>

      {formError && (
        <div role="alert" className={styles.error}>
          {formError}
        </div>
      )}

      <div className={styles.field}>
        <label htmlFor="email" className={styles.label}>
          {t("emailLabel")}
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
          }}
          required
          autoComplete="email"
          className={styles.input}
          disabled={mutation.isPending}
        />
      </div>

      <div className={styles.field}>
        <label htmlFor="password" className={styles.label}>
          {t("passwordLabel")}
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
          }}
          required
          minLength={8}
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          className={styles.input}
          disabled={mutation.isPending}
        />
      </div>

      {mode === "register" && (
        <div className={styles.field}>
          <label htmlFor="displayName" className={styles.label}>
            {t("displayNameLabel")}
          </label>
          <input
            id="displayName"
            type="text"
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
            }}
            maxLength={100}
            autoComplete="name"
            className={styles.input}
            disabled={mutation.isPending}
          />
        </div>
      )}

      <button
        type="submit"
        disabled={mutation.isPending}
        className={styles.submit}
      >
        {mode === "login" ? t("loginButton") : t("registerButton")}
        {mutation.isPending && (
          <span className={styles.spinner} aria-hidden="true" />
        )}
      </button>

      <p className={styles.switch}>
        {mode === "login" ? t("noAccount") : t("hasAccount")}{" "}
        <button
          type="button"
          onClick={() => {
            const nextUrl = sanitizeNextUrl(
              searchParams.get("next"),
              `/${locale}/materials`
            );
            router.replace(
              mode === "login"
                ? `/${locale}/register?next=${encodeURIComponent(nextUrl)}`
                : `/${locale}/login?next=${encodeURIComponent(nextUrl)}`
            );
          }}
          className={styles.switchLink}
        >
          {mode === "login" ? t("registerButton") : t("loginButton")}
        </button>
      </p>
    </form>
  );
}
