import "@grasp/primitives/tokens.css";
import "@/shared/styles/globals.css";
import type { ReactNode } from "react";
import { QueryProvider } from "@/shared/api/query-provider";

export const runtime = "nodejs";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
