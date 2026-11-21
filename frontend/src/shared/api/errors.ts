import type { components } from './schema';

export type ErrorCode = components['schemas']['ErrorCode'];
export type ErrorResponse = components['schemas']['ErrorResponse'];

// Use a valid error code from the new schema as default
export const DEFAULT_ERROR_CODE: ErrorCode = 'internal_server_error';

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: ErrorCode;
  public readonly details?: Record<string, unknown>;

  constructor(
    status: number,
    code: ErrorCode = DEFAULT_ERROR_CODE,
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
      const typed = payload as ErrorResponse;
      return new ApiError(
        status,
        typed.error_code,
        typeof typed.detail === 'string' ? typed.detail : 'API Error',
        undefined // details not in ErrorResponse
      );
    }
    return new ApiError(status, DEFAULT_ERROR_CODE, 'Unexpected error format');
  }
}
