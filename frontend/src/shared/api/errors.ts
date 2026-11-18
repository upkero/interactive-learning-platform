import type { components } from './schema';

export type ErrorCode = components['schemas']['ErrorCode'];
export type ApiErrorPayload = components['schemas']['ApiErrorPayload'];

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: ErrorCode;
  public readonly details?: Record<string, unknown>;

  constructor(
    status: number,
    code: ErrorCode = 'unknown_error',
    message = 'API Error',
    details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  static fromPayload(status: number, payload: unknown): ApiError {
    if (
      typeof payload === 'object' &&
      payload !== null &&
      'error_code' in payload &&
      typeof (payload as Record<string, unknown>).error_code === 'string'
    ) {
      const typed = payload as ApiErrorPayload;
      return new ApiError(status, typed.error_code, typed.message || 'API Error', typed.details);
    }
    return new ApiError(status, 'unknown_error', 'Unexpected error format');
  }
}
