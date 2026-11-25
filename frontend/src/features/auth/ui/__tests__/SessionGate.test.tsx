import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SessionGate } from '../SessionGate';
import { useMe } from '@/entities/user';
import { apiClient } from '@/shared/api/client';
import { NextIntlClientProvider } from 'next-intl';

// Mock next/navigation BEFORE next-intl/navigation is imported
const { mockUseRouter, mockUsePathname, mockUseSearchParams } = vi.hoisted(() => ({
  mockUseRouter: vi.fn(),
  mockUsePathname: vi.fn(),
  mockUseSearchParams: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: mockUseRouter,
  usePathname: mockUsePathname,
  useSearchParams: mockUseSearchParams,
  useParams: vi.fn(),
  redirect: vi.fn(),
  notFound: vi.fn(),
  permanentRedirect: vi.fn(),
}));

// Mock next-intl/navigation BEFORE it's imported by shared/i18n/navigation
vi.mock('next-intl/navigation', () => ({
  createNavigation: () => ({
    Link: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={href} {...props}>{children}</a>,
    usePathname: mockUsePathname,
    useRouter: mockUseRouter,
    useSearchParams: mockUseSearchParams,
    getPathname: vi.fn(),
    redirect: vi.fn(),
  }),
}));

// Mock dependencies
vi.mock('@/entities/user');
vi.mock('@/shared/api/client');

const mockUseMe = vi.mocked(useMe);
const mockApiClient = vi.mocked(apiClient);

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <NextIntlClientProvider locale="ru" messages={{ common: {}, errors: {} }}>
        {children}
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
};

const mockUser = {
  id: '1',
  email: 'test@example.com',
  locale: 'ru' as const,
  display_name: null,
  created_at: new Date().toISOString(),
  notify_email: false,
  last_answers: null,
};

const createMockUseMe = (overrides: Partial<{
  data: typeof mockUser;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  isSuccess: boolean;
}> = {}) => {
  const isLoading = overrides.isLoading ?? false;
  const isError = overrides.isError ?? false;
  const isSuccess = overrides.isSuccess ?? (!isLoading && !isError);
  const data = overrides.data ?? (isSuccess ? mockUser : undefined);
  const error = overrides.error ?? null;

  const result = {
    data,
    isLoading,
    isError,
    error,
    isSuccess,
    isPending: isLoading,
    refetch: vi.fn(),
    status: isLoading ? 'pending' : (isError ? 'error' : 'success'),
    fetchStatus: 'idle',
    failureCount: 0,
    failureReason: null,
    dataUpdatedAt: 0,
    errorUpdatedAt: 0,
    isStale: false,
    isFetching: false,
    isRefetching: false,
    isLoadingError: isError,
    isRefetchError: false,
    isPlaceholderData: false,
    remove: vi.fn(),
    errorUpdateCount: 0,
    isFetched: true,
    isFetchedAfterMount: true,
    isInitialLoading: isLoading,
    isPaused: false,
    isEnabled: true,
  };
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return, @typescript-eslint/no-explicit-any
  return result as any;
};

describe('SessionGate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRouter.mockReturnValue({ replace: vi.fn(), push: vi.fn() });
    mockUsePathname.mockReturnValue('/ru/materials');
    mockUseSearchParams.mockReturnValue(new URLSearchParams());
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it('shows loader while loading', () => {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-argument
    mockUseMe.mockReturnValue(createMockUseMe({ isLoading: true, isSuccess: false }));

    render(<SessionGate><div>Children</div></SessionGate>, { wrapper: createWrapper() });
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('redirects to login on 401 error', async () => {
    const apiError = new Error('Unauthorized') as Error & { status: number };
    apiError.status = 401;

    // eslint-disable-next-line @typescript-eslint/no-unsafe-argument
    mockUseMe.mockReturnValue(createMockUseMe({ isLoading: false, isError: true, error: apiError, isSuccess: false }));

    mockApiClient.POST.mockResolvedValue({ data: { status: 'ok' }, response: { ok: true } });

    render(<SessionGate><div>Children</div></SessionGate>, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockApiClient.POST).toHaveBeenCalledWith('/api/v1/auth/logout');
    });
  });

  it('shows error message on non-401 error', () => {
    const apiError = new Error('Server Error') as Error & { status: number; code: string };
    apiError.status = 500;
    apiError.code = 'internal_server_error';

    // eslint-disable-next-line @typescript-eslint/no-unsafe-argument
    mockUseMe.mockReturnValue(createMockUseMe({ isLoading: false, isError: true, error: apiError, isSuccess: false }));

    render(<SessionGate><div>Children</div></SessionGate>, { wrapper: createWrapper() });

    expect(screen.getByRole('alert')).toBeInTheDocument();
    // The error is not an ApiError instance, so it falls back to unknown_error
    expect(screen.getByText('errors.unknown_error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.retry' })).toBeInTheDocument();
  });

  it('renders children when user is authenticated', () => {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-argument
    mockUseMe.mockReturnValue(createMockUseMe());

    render(<SessionGate><div>Children</div></SessionGate>, { wrapper: createWrapper() });
    expect(screen.getByText('Children')).toBeInTheDocument();
  });

  it('does not call logout twice on 401 (single flight)', async () => {
    const apiError = new Error('Unauthorized') as Error & { status: number };
    apiError.status = 401;

    // eslint-disable-next-line @typescript-eslint/no-unsafe-argument
    mockUseMe.mockReturnValue(createMockUseMe({ isLoading: false, isError: true, error: apiError, isSuccess: false }));

    mockApiClient.POST.mockResolvedValue({ data: { status: 'ok' }, response: { ok: true } });

    render(<SessionGate><div>Children</div></SessionGate>, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockApiClient.POST).toHaveBeenCalledTimes(1);
    });

    // The single-flight protection is handled by the logoutInProgress flag in query-provider
    // and the useEffect dependency array in SessionGate
    expect(mockApiClient.POST).toHaveBeenCalledTimes(1);
  });
});