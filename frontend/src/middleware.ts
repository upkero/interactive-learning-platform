import { NextResponse, type NextRequest } from "next/server";
import createIntlMiddleware from "next-intl/middleware";
import { routing } from "@/shared/i18n/routing";

const intlMiddleware = createIntlMiddleware(routing);

// Session cookie name - matches backend AUTH_SESSION_COOKIE_NAME
const SESSION_COOKIE = "grasp_session";

const PROTECTED_PREFIXES = ["/materials", "/upload", "/documents", "/parts"];

function isProtectedRoute(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export default function middleware(request: NextRequest) {
  const response = intlMiddleware(request);

  const pathname = request.nextUrl.pathname;

  // Extract locale using routing config
  const localeMatch = routing.locales.find((l) =>
    pathname.startsWith(`/${l}/`)
  );
  const locale = localeMatch || routing.defaultLocale;
  const localePrefix = `/${locale}`;
  const localePathname = pathname.slice(localePrefix.length) || "/";

  if (isProtectedRoute(localePathname)) {
    const sessionCookie = request.cookies.get(SESSION_COOKIE)?.value;

    if (!sessionCookie || sessionCookie.trim() === "") {
      const loginUrl = new URL(`/${locale}/login`, request.url);
      // Preserve the original path and query as `next` parameter
      loginUrl.searchParams.set("next", pathname + request.nextUrl.search);
      return NextResponse.redirect(loginUrl);
    }
  }

  return response;
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
