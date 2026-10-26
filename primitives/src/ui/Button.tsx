import type { ButtonHTMLAttributes } from "react";

import styles from "./Button.module.css";

export interface ButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  label: string;
  variant?: "primary" | "secondary" | "ghost";
}

export function Button({
  label,
  type = "button",
  variant = "primary",
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      className={[styles.button, styles[variant], className]
        .filter(Boolean)
        .join(" ")}
      type={type}
    >
      {label}
    </button>
  );
}
