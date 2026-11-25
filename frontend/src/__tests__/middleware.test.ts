import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NextRequest } from 'next/server';

// We need to test the middleware logic, so we'll extract the core logic
const SESSION_COOKIE = 'grasp_session';
const PROTECTED_PREFIXES = ['/materials', '/upload', '/documents', '/parts'];

function isProtectedRoute(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

const locales = ['ru', 'en'] as const;
const defaultLocale = 'ru';

function extractLocale(pathname: string): string {
  const localeMatch = locales.find((l) => pathname.startsWith(`/${l}/`));
  return localeMatch || defaultLocale;
}

function getLocalePathname(pathname: string): string {
  const locale = extractLocale(pathname);
  const localePrefix = `/${locale}`;
  return pathname.slice(localePrefix.length) || '/';
}

function hasValidSession(request: NextRequest): boolean {
  const sessionCookie = request.cookies.get(SESSION_COOKIE)?.value;
  return !!(sessionCookie && sessionCookie.trim() !== '');
}

describe('middleware logic', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('identifies protected routes correctly', () => {
    expect(isProtectedRoute('/materials')).toBe(true);
    expect(isProtectedRoute('/upload')).toBe(true);
    expect(isProtectedRoute('/documents/123')).toBe(true);
    expect(isProtectedRoute('/parts/456')).toBe(true);
    expect(isProtectedRoute('/login')).toBe(false);
    expect(isProtectedRoute('/register')).toBe(false);
    expect(isProtectedRoute('/')).toBe(false);
  });

  it('extracts locale from pathname using routing locales', () => {
    expect(extractLocale('/ru/materials')).toBe('ru');
    expect(extractLocale('/en/upload')).toBe('en');
    expect(extractLocale('/ru/documents/123')).toBe('ru');
    expect(extractLocale('/invalid/path')).toBe('ru'); // default
    expect(extractLocale('/')).toBe('ru'); // default
  });

  it('strips locale prefix correctly', () => {
    expect(getLocalePathname('/ru/materials')).toBe('/materials');
    expect(getLocalePathname('/en/upload')).toBe('/upload');
    expect(getLocalePathname('/ru/documents/123/topics')).toBe('/documents/123/topics');
    expect(getLocalePathname('/ru/')).toBe('/');
  });

  it('detects valid session cookie', () => {
    const request = new NextRequest('http://localhost/ru/materials', {
      headers: { cookie: 'grasp_session=abc123' },
    });
    expect(hasValidSession(request)).toBe(true);
  });

  it('rejects missing session cookie', () => {
    const request = new NextRequest('http://localhost/ru/materials', {
      headers: { cookie: 'other_cookie=abc123' },
    });
    expect(hasValidSession(request)).toBe(false);
  });

  it('rejects empty session cookie', () => {
    const request = new NextRequest('http://localhost/ru/materials', {
      headers: { cookie: 'grasp_session=' },
    });
    expect(hasValidSession(request)).toBe(false);
  });

  it('rejects whitespace-only session cookie', () => {
    const request = new NextRequest('http://localhost/ru/materials', {
      headers: { cookie: 'grasp_session=   ' },
    });
    expect(hasValidSession(request)).toBe(false);
  });

  it('rejects cookie with different name', () => {
    const request = new NextRequest('http://localhost/ru/materials', {
      headers: { cookie: 'xgrasp_session=abc123' },
    });
    expect(hasValidSession(request)).toBe(false);
  });

  it('preserves next parameter with query string', () => {
    const request = new NextRequest('http://localhost/ru/documents/123?tab=quiz', {
      headers: { cookie: 'other=value' },
    });

    const locale = extractLocale(request.nextUrl.pathname);
    const localePathname = getLocalePathname(request.nextUrl.pathname);

    expect(locale).toBe('ru');
    expect(localePathname).toBe('/documents/123');

    // The redirect URL would be:
    const loginUrl = new URL(`/${locale}/login`, request.url);
    loginUrl.searchParams.set('next', request.nextUrl.pathname + request.nextUrl.search);
    expect(loginUrl.toString()).toBe('http://localhost/ru/login?next=%2Fru%2Fdocuments%2F123%3Ftab%3Dquiz');
  });
});