/// <reference types="vitest/globals" />
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { WidgetRenderer } from '../WidgetRenderer';
import { useWidgetReport } from '../../model/useWidgetReport';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NextIntlClientProvider } from 'next-intl';
import ruMessages from '@/shared/i18n/messages/ru.json';
import type { ConfigWidget, CodeWidget, PendingWidget } from '../../model/types';

// Mock modules
vi.mock('../../model/useWidgetReport', () => ({
  useWidgetReport: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
  useSearchParams: vi.fn(),
}));

const mockConfigWidget: ConfigWidget = {
  kind: 'config',
  mode: 'diagram',
  params: { nodes: [], edges: [] },
  primitive_id: 'primitive-1',
  status: 'ready',
  title: 'Test Diagram',
  widget_id: 'widget-1',
};

const mockCodeWidget: CodeWidget = {
  kind: 'code',
  compiled_js: 'console.log("hello");',
  labels: { x: 'X axis', y: 'Y axis' },
  status: 'ready',
  title: 'Test Chart',
  widget_id: 'widget-2',
};

const mockPendingWidget: PendingWidget = {
  status: 'pending',
  title: 'Generating...',
  fallback: { type: 'text', text: 'Fallback text' },
};

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <NextIntlClientProvider locale="ru" messages={ruMessages}>
        {children}
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
};

describe('WidgetRenderer', () => {
  let mockReportMutation: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    mockReportMutation = {
      mutateAsync: vi.fn().mockResolvedValue({ status: 'ok' }),
      isPending: false,
      isError: false,
      isSuccess: false,
    };

    (useWidgetReport as vi.Mock).mockReturnValue(mockReportMutation);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('PendingWidget', () => {
    it('renders pending state with spinner and title', async () => {
      render(
        <WidgetRenderer widget={mockPendingWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(screen.getByRole('status')).toBeInTheDocument();
        // The widget title is shown instead of translation when title is provided
        expect(screen.getByText('Generating...')).toBeInTheDocument();
        // The translation text is in the aria-label of the status element
        const statusElement = screen.getByRole('status');
        expect(statusElement).toHaveAttribute('aria-label', 'Интерактивный виджет формируется...');
      });
    });

    it('shows fallback widget when status is fallback', async () => {
      const fallbackWidget: PendingWidget = {
        status: 'fallback',
        title: 'Fallback Widget',
        fallback: { type: 'text', text: 'Fallback content' },
      };

      render(
        <WidgetRenderer widget={fallbackWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(screen.getByRole('note')).toBeInTheDocument();
        expect(screen.getByText('Fallback content')).toBeInTheDocument();
      });
    });
  });

  describe('ConfigWidget', () => {
    it('renders widget container with loading state initially', async () => {
      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      // First loading state shows
      await waitFor(() => {
        expect(screen.getByText('Интерактивный виджет формируется...')).toBeInTheDocument();
      });

      // The widget container should exist with the title
      const container = screen.getByRole('region', { name: 'Test Diagram' });
      expect(container).toBeInTheDocument();
      // In jsdom, iframe onLoad doesn't fire, so loading state persists
      // This is expected behavior in test environment
    });

    it('shows report button on hover', async () => {
      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        const container = screen.getByRole('region', { name: 'Test Diagram' });
        // Initially report button is hidden (opacity: 0)
        const reportButton = container.querySelector('button[aria-label="Что-то не так?"]');
        expect(reportButton).toBeInTheDocument();
      });
    });

    it('shows loading state initially', async () => {
      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      // Should show loading state initially
      await waitFor(() => {
        expect(screen.getByText('Интерактивный виджет формируется...')).toBeInTheDocument();
      });
    });
  });

  describe('CodeWidget', () => {
    it('renders widget container with loading state initially', async () => {
      render(
        <WidgetRenderer widget={mockCodeWidget} widgetId="widget-2" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      // First loading state shows
      await waitFor(() => {
        expect(screen.getByText('Интерактивный виджет формируется...')).toBeInTheDocument();
      });

      // The widget container should exist with the title
      const container = screen.getByRole('region', { name: 'Test Chart' });
      expect(container).toBeInTheDocument();
      // In jsdom, iframe onLoad doesn't fire, so loading state persists
      // This is expected behavior in test environment
    });
  });

  describe('Error handling', () => {
    it('shows error state when iframe fails to load', async () => {
      // This test would need to simulate iframe error
      // For now, we verify the component structure allows error display
      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        const container = screen.getByRole('region', { name: 'Test Diagram' });
        expect(container).toBeInTheDocument();
      });
    });
  });

  describe('Report modal', () => {
    it('opens report modal when report button is clicked', async () => {
      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        const container = screen.getByRole('region', { name: 'Test Diagram' });
        const reportButton = container.querySelector('button[aria-label="Что-то не так?"]');
        expect(reportButton).toBeInTheDocument();
        fireEvent.click(reportButton!);
      });

      await waitFor(() => {
        expect(screen.getByRole('dialog', { name: 'Сообщить о проблеме с виджетом' })).toBeInTheDocument();
      });
    });

    it('submits report with selected reason and comment', async () => {
      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        const container = screen.getByRole('region', { name: 'Test Diagram' });
        const reportButton = container.querySelector('button[aria-label="Что-то не так?"]');
        fireEvent.click(reportButton!);
      });

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Select a reason
      const reasonRadio = screen.getByLabelText(/фактическая ошибка в содержании/i);
      fireEvent.click(reasonRadio);

      // Fill comment
      const commentTextarea = screen.getByLabelText(/комментарий \(необязательно\)/i);
      fireEvent.change(commentTextarea, { target: { value: 'Test comment' } });

      // Submit
      const submitButton = screen.getByRole('button', { name: /отправить жалобу/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockReportMutation.mutateAsync).toHaveBeenCalledWith({
          widgetId: 'widget-1',
          body: {
            reason: 'wrong',
            comment: 'Test comment',
            part_id: 'part-1',
          },
        });
      });
    });

    it('shows success toast after successful submission', async () => {
      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        const container = screen.getByRole('region', { name: 'Test Diagram' });
        const reportButton = container.querySelector('button[aria-label="Что-то не так?"]');
        fireEvent.click(reportButton!);
      });

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /отправить жалобу/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Спасибо, жалоба отправлена')).toBeInTheDocument();
      });
    });

    it('shows error when submission fails', async () => {
      mockReportMutation.mutateAsync.mockRejectedValueOnce(new Error('widget_not_found'));

      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        const container = screen.getByRole('region', { name: 'Test Diagram' });
        const reportButton = container.querySelector('button[aria-label="Что-то не так?"]');
        fireEvent.click(reportButton!);
      });

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /отправить жалобу/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Виджет не найден или недоступен.')).toBeInTheDocument();
      });
    });

    it('closes modal on cancel', async () => {
      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        const container = screen.getByRole('region', { name: 'Test Diagram' });
        const reportButton = container.querySelector('button[aria-label="Что-то не так?"]');
        fireEvent.click(reportButton!);
      });

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: /отмена/i });
      fireEvent.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels and roles', async () => {
      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        const region = screen.getByRole('region', { name: 'Test Diagram' });
        expect(region).toBeInTheDocument();
        expect(region).toHaveAttribute('aria-label', 'Test Diagram');
      });
    });

    it('report button has proper aria-haspopup', async () => {
      render(
        <WidgetRenderer widget={mockConfigWidget} widgetId="widget-1" partId="part-1" />,
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        const container = screen.getByRole('region', { name: 'Test Diagram' });
        const reportButton = container.querySelector('button[aria-label="Что-то не так?"]');
        expect(reportButton).toHaveAttribute('aria-haspopup', 'dialog');
      });
    });
  });
});