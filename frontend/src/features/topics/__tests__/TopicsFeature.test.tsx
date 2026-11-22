/// <reference types="vitest/globals" />
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TopicsFeature } from '../ui/TopicsFeature';
import { useDocumentTopics } from '@/entities/document';
import { useQuota } from '@/entities/user';
import { useDocumentStatusGuard } from '@/entities/document/guard/useDocumentStatusGuard';
import { useRouter, useSearchParams } from 'next/navigation';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NextIntlClientProvider } from 'next-intl';
import ruMessages from '@/shared/i18n/messages/ru.json';

// Mock modules
vi.mock('@/entities/document', () => ({
  useDocumentTopics: vi.fn(),
}));

vi.mock('@/entities/user', () => ({
  useQuota: vi.fn(),
}));

vi.mock('@/entities/document/guard/useDocumentStatusGuard', () => ({
  useDocumentStatusGuard: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
  useSearchParams: vi.fn(),
}));

const mockTopics = [
  {
    id: 'topic-1',
    title: 'Topic 1',
    tokens: 10,
    children: [],
  },
  {
    id: 'topic-2',
    title: 'Topic 2',
    tokens: 20,
    children: [],
  },
];

const mockQuota = { available: 50 };

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

describe('TopicsFeature - URL topics parameter', () => {
  let mockRouter: ReturnType<typeof vi.fn>;
  let mockSearchParams: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    mockRouter = {
      push: vi.fn(),
      replace: vi.fn(),
    };

    mockSearchParams = vi.fn().mockReturnValue(new URLSearchParams());

    (useRouter as vi.Mock).mockReturnValue(mockRouter);
    (useSearchParams as vi.Mock).mockReturnValue(mockSearchParams);
    (useDocumentTopics as vi.Mock).mockReturnValue({
      data: mockTopics,
      isPending: false,
      isError: false,
    });
    (useQuota as vi.Mock).mockReturnValue({
      data: { available: 50 },
      isPending: false,
      isError: false,
    });
    (useDocumentStatusGuard as vi.Mock).mockReturnValue({
      isLoading: false,
      error: null,
      hasRedirected: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders topics list from API', async () => {
    const params = new URLSearchParams({ topics: 'topic-1' });
    (useSearchParams as vi.Mock).mockReturnValue(params);

    render(<TopicsFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      const title = screen.getByText('Topic 1');
      expect(title).toBeInTheDocument();
    });
  });

  it('updates URL when selection changes (debounced)', async () => {
    // This test verifies the URL update logic works
    // Note: The debounce timing makes this test complex with fake timers
    // We verify the component renders and the router is available
    const params = new URLSearchParams();
    (useSearchParams as vi.Mock).mockReturnValue(params);

    render(<TopicsFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Topic 1')).toBeInTheDocument();
    });

    // Click on a topic checkbox to select it
    const checkbox1 = screen.getByRole('checkbox', { name: /topic 1/i });
    fireEvent.click(checkbox1);

    // The debounced URL update is tested by verifying the router.replace is called
    // We use a longer timeout to allow the debounce to complete
    await waitFor(() => {
      expect(mockRouter.replace).toHaveBeenCalledWith(
        expect.stringContaining('topics=topic-1')
      );
    }, { timeout: 15000 });
  });

  it('navigates to questions with topics in URL on next click', async () => {
    const params = new URLSearchParams({ topics: 'topic-1,topic-2' });
    (useSearchParams as vi.Mock).mockReturnValue(params);

    render(<TopicsFeature documentId="doc-1" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Topic 1')).toBeInTheDocument();
    });

    // Click next button
    const nextButton = screen.getByRole('link', { name: /далее/i });
    fireEvent.click(nextButton);

    expect(mockRouter.push).toHaveBeenCalledWith(
      '/ru/documents/doc-1/questions?topics=topic-1,topic-2'
    );
  });
});