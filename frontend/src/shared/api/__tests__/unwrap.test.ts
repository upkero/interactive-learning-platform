import { describe, it, expect, vi, beforeEach } from 'vitest';
import { unwrap, ApiError, isApiError } from '../errors';

describe('unwrap', () => {
  const createMockResponse = (ok: boolean, status: number, data: unknown = null, error?: unknown) => {
    const response = new Response(JSON.stringify(data), { status, statusText: ok ? 'OK' : 'Error' });
    return {
      data,
      response,
      error,
    };
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns data on 2xx response', async () => {
    const promise = Promise.resolve(createMockResponse(true, 200, { id: '1', name: 'Test' }));
    const result = await unwrap(promise);
    expect(result).toEqual({ id: '1', name: 'Test' });
  });

  it('throws ApiError with error_code on 4xx response with body', async () => {
    const apiError = new ApiError(401, 'invalid_credentials', 'Invalid email or password');
    const promise = Promise.resolve(createMockResponse(false, 401, null, apiError));

    await expect(unwrap(promise)).rejects.toThrow(ApiError);
    await expect(unwrap(promise)).rejects.toMatchObject({
      status: 401,
      code: 'invalid_credentials',
    });
  });

  it('throws ApiError with unknown_error on 5xx response without body', async () => {
    const promise = Promise.resolve(createMockResponse(false, 500, null));

    await expect(unwrap(promise)).rejects.toThrow(ApiError);
    await expect(unwrap(promise)).rejects.toMatchObject({
      status: 500,
      code: 'unknown_error',
    });
  });

  it('throws ApiError with network_error on fetch TypeError', async () => {
    const networkError = new TypeError('Failed to fetch');
    const promise = Promise.reject(networkError);

    await expect(unwrap(promise)).rejects.toThrow(ApiError);
    await expect(unwrap(promise)).rejects.toMatchObject({
      status: 0,
      code: 'network_error',
    });
  });

  it('throws ApiError with unknown_error on 2xx with null data', async () => {
    const promise = Promise.resolve(createMockResponse(true, 200, null));

    await expect(unwrap(promise)).rejects.toThrow(ApiError);
    await expect(unwrap(promise)).rejects.toMatchObject({
      status: 200,
      code: 'unknown_error',
    });
  });

  it('throws ApiError with server error code on 4xx with payload', async () => {
    const apiError = new ApiError(402, 'quota_exceeded', 'Quota exceeded');
    const promise = Promise.resolve(createMockResponse(false, 402, null, apiError));

    await expect(unwrap(promise)).rejects.toThrow(ApiError);
    await expect(unwrap(promise)).rejects.toMatchObject({
      status: 402,
      code: 'quota_exceeded',
    });
  });
});

describe('isApiError', () => {
  it('returns true for ApiError instances', () => {
    expect(isApiError(new ApiError(401, 'invalid_credentials'))).toBe(true);
  });

  it('returns false for regular Errors', () => {
    expect(isApiError(new Error('regular error'))).toBe(false);
  });

  it('returns false for TypeError', () => {
    expect(isApiError(new TypeError('network error'))).toBe(false);
  });

  it('returns false for plain objects', () => {
    expect(isApiError({ status: 401, code: 'invalid_credentials' })).toBe(false);
  });

  it('returns false for null/undefined', () => {
    expect(isApiError(null)).toBe(false);
    expect(isApiError(undefined)).toBe(false);
  });
});