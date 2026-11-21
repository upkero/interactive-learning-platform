import { NextResponse, type NextRequest } from 'next/server';
import createIntlMiddleware from 'next-intl/middleware';
import { routing } from '@/shared/i18n/routing';

const intlMiddleware = createIntlMiddleware(routing);

const PROTECTED_PREFIXES = ['/materials', '/upload', '/documents', '/parts'];

function isProtectedRoute(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export default function middleware(request: NextRequest) {
  const response = intlMiddleware(request);

  const pathname = request.nextUrl.pathname;
  const localeMatch = pathname.match(/^\/(ru|en)/);
  const locale = localeMatch ? localeMatch[1] : routing.defaultLocale;
  const localePathname = pathname.slice(locale.length + 1) || '/';

  if (isProtectedRoute(localePathname)) {
    const sessionCookie = request.headers.get('cookie') || '';
    const hasSession = sessionCookie.includes('grasp_session=');

    if (!hasSession) {
      const loginUrl = new URL(`/${locale}/login`, request.url);
      return NextResponse.redirect(loginUrl);
    }
  }

  return response;
}

export const config = {
  matcher: ['/((?!api|_next|_vercel|.*\\..*).*)'],
};
