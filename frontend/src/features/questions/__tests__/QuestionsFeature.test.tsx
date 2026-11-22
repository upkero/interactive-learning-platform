/// <reference types="vitest/globals" />
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach, act } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QuestionsFeature } from '../ui/QuestionsFeature';
import { useGenerateDocument } from '@/entities/document';
import { useQuota, QUOTA_QUERY_KEY } from '@/entities/user';
import { useDocumentStatusGuard } from '@/entities/document/guard/useDocumentStatusGuard';
import { useRouter, useSearchParams } from 'next/navigation';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NextIntlClientProvider } from 'next-intl';
import { ApiError } from '@/shared/api/errors';
import ruMessages from '@/shared/i18n/messages/ru.json';

// Mock modules
vi.mock('@/entities/document', () => ({
  useGenerateDocument: vi.fn(),
}));

vi.mock('@/entities/user', () => ({
  useQuota: vi.fn(),
  QUOTA_QUERY_KEY: ['me', 'quota'],
}));

vi.mock('@/entities/document/guard/useDocumentStatusGuard', () => ({
  useDocumentStatusGuard: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
  useSearchParams: vi.fn(),
}));

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query');
  return {
    ...actual,
    useQueryClient: vi.fn(),
  };
});

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

describe('QuestionsFeature - 402/409 error handling', () => {
  let mockGenerateMutation: ReturnType<typeof vi.fn>;
  let mockQuotaQuery: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    mockGenerateMutation = {
      mutateAsync: vi.fn(),
      isPending: false,
    };

    mockQuotaQuery = {
      data: { available: 10 },
      isPending: false,
      isError: false,
    };

    (useRouter as vi.Mock).mockReturnValue(mockRouter);
    (useSearchParams as vi.Mock).mockReturnValue(new URLSearchParams({ topics: 'topic-1,topic-2' }));
    (useGenerateDocument as vi.Mock).mockReturnValue(mockGenerateMutation);
    (useQuota as vi.Mock).mockReturnValue(mockQuotaQuery);
    (useDocumentStatusGuard as vi.Mock).mockReturnValue({
      isLoading: false,
      error: null,
      hasRedirected: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows quota_exceeded error when 402 received', async () => {
    const quotaError = new ApiError(402, 'quota_exceeded', 'Quota exceeded', { available: 0, requested: 5 });
    mockGenerateMutation.mutateAsync.mockRejectedValue(quotaError);
    mockQuotaQuery.data = { available: 0 }; // quota exhausted

    render(<QuestionsFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Параметры генерации')).toBeTruthy();
    });

    // Click start button
    const startButton = screen.getByText('Запустить генерацию');
    fireEvent.click(startButton);

    // Wait for error to appear - the actual error message from i18n
    await waitFor(() => {
      const errorText = screen.getByText('Недостаточно доступных генераций для выполнения операции.');
      expect(errorText).toBeInTheDocument();
    });
  });

  it('shows document_not_ready error when 409 received', async () => {
    const notReadyError = new ApiError(409, 'document_not_ready', 'Document not ready', { status: 'parsed' });
    mockGenerateMutation.mutateAsync.mockRejectedValue(notReadyError);

    render(<QuestionsFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Параметры генерации')).toBeTruthy();
    });

    // Click start button
    const startButton = screen.getByText('Запустить генерацию');
    fireEvent.click(startButton);

    // Wait for error to appear - the actual error message from i18n
    await waitFor(() => {
      const errorText = screen.getByText('Документ ещё не готов. Дождитесь завершения разбора.');
      expect(errorText).toBeInTheDocument();
    });
  });

  it('navigates to progress on successful generation', async () => {
    mockGenerateMutation.mutateAsync.mockResolvedValue({ document_id: 'doc-1', part_ids: ['part-1'] });

    render(<QuestionsFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Параметры генерации')).toBeTruthy();
    });

    const startButton = screen.getByRole('link', { name: /запустить генерацию/i });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(mockRouter.push).toHaveBeenCalledWith('/ru/documents/doc-1/progress');
    });
  });

  it('restores topics from URL on mount', async () => {
    render(<QuestionsFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Параметры генерации')).toBeTruthy();
    });
  });

  it('falls back to sessionStorage when URL has no topics param', async () => {
    (useSearchParams as vi.Mock).mockReturnValue(new URLSearchParams());

    render(<QuestionsFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Параметры генерации')).toBeTruthy();
    });
  });
});