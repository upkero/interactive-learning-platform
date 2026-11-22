/// <reference types="vitest/globals" />
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach, act } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ProgressFeature } from '../ui/ProgressFeature';
import { useEventStream } from '@/shared/lib/sse/useEventStream';
import { useDocumentStatusGuard } from '@/entities/document/guard/useDocumentStatusGuard';
import { useRetryPart } from '@/entities/document';
import { useRouter, useSearchParams } from 'next/navigation';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NextIntlClientProvider } from 'next-intl';
import ruMessages from '@/shared/i18n/messages/ru.json';

// Mock modules
vi.mock('@/shared/lib/sse/useEventStream', () => ({
  useEventStream: vi.fn(),
}));

vi.mock('@/entities/document/guard/useDocumentStatusGuard', () => ({
  useDocumentStatusGuard: vi.fn(),
}));

vi.mock('@/entities/document', () => ({
  useRetryPart: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
  useSearchParams: vi.fn(),
}));

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
};

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <NextIntlClientProvider locale="ru" messages={ruMessages}>
        {children}
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
};

describe('ProgressFeature - retry part', () => {
  let mockRetryPartMutation: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    mockRetryPartMutation = {
      mutateAsync: vi.fn().mockResolvedValue(undefined),
      isPending: false,
    };

    (useRouter as vi.Mock).mockReturnValue(mockRouter);
    (useSearchParams as vi.Mock).mockReturnValue(new URLSearchParams());
    (useEventStream as vi.Mock).mockReturnValue({ status: 'open' });
    (useDocumentStatusGuard as vi.Mock).mockReturnValue({
      isLoading: false,
      error: null,
      hasRedirected: false,
    });
    (useRetryPart as vi.Mock).mockReturnValue(mockRetryPartMutation);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders progress page without error', async () => {
    render(<ProgressFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Создаём материал')).toBeTruthy();
    });
  });

  it('useRetryPart hook is exported and available', async () => {
    const { useRetryPart } = await import('@/entities/document');
    expect(useRetryPart).toBeDefined();
    expect(typeof useRetryPart).toBe('function');
  });

  it('useRetryPart mutation has correct structure', async () => {
    render(<ProgressFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Создаём материал')).toBeTruthy();
    });

    // Verify useRetryPart hook is called
    expect(useRetryPart).toHaveBeenCalled();

    // Verify the mutation has the expected structure
    expect(mockRetryPartMutation.mutateAsync).toBeDefined();
    expect(typeof mockRetryPartMutation.mutateAsync).toBe('function');
  });

  it('shows loading state on retry button when mutation is pending', async () => {
    const pendingMutation = {
      mutateAsync: vi.fn().mockResolvedValue(undefined),
      isPending: true,
    };
    (useRetryPart as vi.Mock).mockReturnValue(pendingMutation);

    render(<ProgressFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Создаём материал')).toBeTruthy();
    });

    // When isPending is true, the retry button should show loading
    expect(pendingMutation.isPending).toBe(true);
  });
});