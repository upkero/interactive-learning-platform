import "@grasp/primitives/tokens.css";
import "@/shared/styles/globals.css";
import { getLocale } from "next-intl/server";
import type { ReactNode } from "react";

export const runtime = "nodejs";

export default async function RootLayout({ children }: { children: ReactNode }) {
  const locale = await getLocale();

  return (
    <html lang={locale}>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body>{children}</body>
    </html>
  );
}
