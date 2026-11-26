import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import { expect, it, vi } from 'vitest';
import { apiClient } from '@/shared/api/client';
import ruMessages from '@/shared/i18n/messages/ru.json';
import { QuizFeature } from '../ui/QuizFeature';

vi.mock('@/shared/api/client', () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

it('submits a seeded-style quiz and returns to the document identified by the API', async () => {
  const partId = '11111111-1111-4111-8111-111111111111';
  const documentId = '22222222-2222-4222-8222-222222222222';
  const quizKey = '3f9a0c1b2d4e';

  vi.mocked(apiClient.GET).mockResolvedValue({
    response: new Response(),
    data: {
      document_id: documentId,
      id: partId,
      index: 0,
      status: 'published',
      title: 'From neurons to layers',
      content: {
        schema_version: 1,
        title: 'From neurons to layers',
        markdown: '',
        quizzes: [
          {
            key: quizKey,
            ref: 'q1',
            type: 'single_choice',
            prompt: 'Which operation does a neuron apply after the weighted sum?',
            options: [{ id: 'a', text: 'Activation' }, { id: 'b', text: 'Pooling' }],
          },
        ],
      },
    },
  });
  vi.mocked(apiClient.POST).mockResolvedValue({
    response: new Response(),
    data: {
      is_correct: true,
      correct_answer: 'a',
      explanation: 'A neuron applies an activation.',
      option_explanations: null,
    },
  });

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <NextIntlClientProvider locale="ru" timeZone="UTC" messages={ruMessages}>
        <QuizFeature partId={partId} />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );

  const activation = await screen.findByRole('radio', { name: 'Activation' });
  const finish = screen.getByRole('button', { name: 'Завершить тест' });
  expect(finish).toBeDisabled();
  fireEvent.click(activation);
  fireEvent.click(finish);

  expect(await screen.findByText('Результат: 1 из 1')).toBeInTheDocument();
  expect(screen.getByText('100%')).toBeInTheDocument();
  expect(screen.getByText(/A neuron applies an activation\./)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Вернуться к конспекту' })).toHaveAttribute(
    'href',
    `/ru/documents/${documentId}`,
  );
  expect(apiClient.POST).toHaveBeenCalledWith('/api/v1/quiz-attempts', {
    body: { part_id: partId, quiz_key: quizKey, answer: 'a' },
  });

  fireEvent.click(screen.getByRole('button', { name: 'Пройти тест заново' }));
  expect(screen.getByRole('radio', { name: 'Activation' })).not.toBeChecked();
  expect(screen.getByRole('button', { name: 'Завершить тест' })).toBeDisabled();
});
