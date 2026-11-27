import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import QuizPage from '@/app/[locale]/(main)/parts/[id]/quiz/page';
import { apiClient } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';
import ruMessages from '@/shared/i18n/messages/ru.json';

vi.mock('@/shared/api/client', () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

const partId = '11111111-1111-4111-8111-111111111111';
const documentId = '22222222-2222-4222-8222-222222222222';

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(cleanup);

async function renderQuiz(quizzes: components['schemas']['PartContentOut']['quizzes']) {
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
        quizzes,
      },
    },
  });

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const page = await QuizPage({ params: Promise.resolve({ id: partId, locale: 'ru' }) });
  render(
    <QueryClientProvider client={queryClient}>
      <NextIntlClientProvider locale="ru" timeZone="UTC" messages={ruMessages}>
        {page}
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

it('submits a seeded-style quiz and returns to the document identified by the API', async () => {
  const quizKey = '3f9a0c1b2d4e';
  vi.mocked(apiClient.POST).mockResolvedValue({
    response: new Response(),
    data: {
      is_correct: true,
      correct_answer: 'a',
      explanation: 'A neuron applies an activation.',
      option_explanations: null,
    },
  });
  await renderQuiz([
    {
      key: quizKey,
      ref: 'q1',
      type: 'single_choice',
      prompt: 'Which operation does a neuron apply after the weighted sum?',
      options: [{ id: 'a', text: 'Activation' }, { id: 'b', text: 'Pooling' }],
    },
  ]);

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

it('posts multiple choice, ordering, and numeric answers in their API formats and explains the results', async () => {
  vi.mocked(apiClient.POST)
    .mockResolvedValueOnce({
      response: new Response(),
      data: { is_correct: true, correct_answer: ['a', 'c'], explanation: null, option_explanations: null },
    })
    .mockResolvedValueOnce({
      response: new Response(),
      data: {
        is_correct: false,
        correct_answer: ['first', 'second', 'third'],
        explanation: 'Validate the result last.',
        option_explanations: null,
      },
    })
    .mockResolvedValueOnce({
      response: new Response(),
      data: {
        is_correct: true,
        correct_answer: -4.2,
        explanation: 'The answer is within tolerance.',
        option_explanations: null,
      },
    });

  await renderQuiz([
    {
      key: 'multiple',
      ref: 'q1',
      type: 'multiple_choice',
      prompt: 'Select the prime numbers.',
      options: [{ id: 'a', text: '2' }, { id: 'b', text: '4' }, { id: 'c', text: '5' }],
    },
    {
      key: 'order',
      ref: 'q2',
      type: 'ordering',
      prompt: 'Order the calculation steps.',
      items: [
        { id: 'first', text: 'Read the input' },
        { id: 'second', text: 'Calculate the result' },
        { id: 'third', text: 'Validate the result' },
      ],
    },
    {
      key: 'number',
      ref: 'q3',
      type: 'numeric',
      prompt: 'What is the displacement?',
      unit: 'm',
    },
  ]);

  fireEvent.click(await screen.findByRole('checkbox', { name: '5' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '4' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '2' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '4' }));
  fireEvent.click(screen.getByRole('button', { name: 'Следующий вопрос' }));

  const firstPosition = screen.getByLabelText('Позиция 1');
  const secondPosition = screen.getByLabelText('Позиция 2');
  const thirdPosition = screen.getByLabelText('Позиция 3');
  fireEvent.change(firstPosition, { target: { value: 'third' } });
  expect(within(secondPosition).getByRole('option', { name: 'Validate the result' })).toBeDisabled();
  fireEvent.change(secondPosition, { target: { value: 'second' } });
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '1');
  fireEvent.change(thirdPosition, { target: { value: 'first' } });
  fireEvent.click(screen.getByRole('button', { name: 'Следующий вопрос' }));

  const numericInput = screen.getByRole('spinbutton', { name: 'Числовой ответ (m)' });
  const finish = screen.getByRole('button', { name: 'Завершить тест' });
  expect(finish).toBeDisabled();
  fireEvent.change(numericInput, { target: { value: '0' } });
  expect(finish).toBeEnabled();
  fireEvent.change(numericInput, { target: { value: '' } });
  expect(finish).toBeDisabled();
  fireEvent.change(numericInput, { target: { value: '-4.25' } });
  fireEvent.click(finish);

  expect(await screen.findByText('Результат: 2 из 3')).toBeInTheDocument();
  expect(apiClient.POST).toHaveBeenCalledTimes(3);
  expect(apiClient.POST).toHaveBeenNthCalledWith(1, '/api/v1/quiz-attempts', {
    body: { part_id: partId, quiz_key: 'multiple', answer: ['c', 'a'] },
  });
  expect(apiClient.POST).toHaveBeenNthCalledWith(2, '/api/v1/quiz-attempts', {
    body: { part_id: partId, quiz_key: 'order', answer: ['third', 'second', 'first'] },
  });
  expect(apiClient.POST).toHaveBeenNthCalledWith(3, '/api/v1/quiz-attempts', {
    body: { part_id: partId, quiz_key: 'number', answer: -4.25 },
  });

  const [submittedOrder, correctOrder] = screen.getAllByRole('list');
  expect(within(submittedOrder).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
    'Validate the result', 'Calculate the result', 'Read the input',
  ]);
  expect(within(correctOrder).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
    'Read the input', 'Calculate the result', 'Validate the result',
  ]);
  expect(screen.getByText(/Validate the result last\./)).toBeInTheDocument();
  expect(screen.getByText('-4.25 m')).toBeInTheDocument();
  expect(screen.getByText('-4.2 m')).toBeInTheDocument();
  expect(screen.getByText(/The answer is within tolerance\./)).toBeInTheDocument();
});
