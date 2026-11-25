import type { components } from "./schema";

export type ServerErrorCode = components["schemas"]["ErrorCode"];
export type ErrorResponse = components["schemas"]["ErrorResponse"];

// Client-side error codes that don't come from the server
export type ClientErrorCode =
  "network_error" | "unknown_error" | ServerErrorCode;

// Use a valid error code from the new schema as default
export const DEFAULT_ERROR_CODE: ServerErrorCode = "internal_server_error";

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: ClientErrorCode;
  public readonly details?: Record<string, unknown>;

  constructor(
    status: number,
    code: ClientErrorCode = DEFAULT_ERROR_CODE,
    message = "API Error",
    details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  static fromPayload(status: number, payload: unknown): ApiError {
    if (
      typeof payload === "object" &&
      payload !== null &&
      "error_code" in payload &&
      typeof (payload as Record<string, unknown>).error_code === "string"
    ) {
      const typed = payload as ErrorResponse;
      return new ApiError(
        status,
        typed.error_code,
        typeof typed.detail === "string" ? typed.detail : "API Error",
        undefined // details not in ErrorResponse
      );
    }
    return new ApiError(status, DEFAULT_ERROR_CODE, "Unexpected error format");
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/**
 * Unwraps the response from openapi-fetch, throwing an ApiError on non-2xx responses.
 * Network errors (TypeError) are converted to ApiError with code 'network_error'.
 * 5xx responses without a valid error body get code 'unknown_error'.
 *
 * Accepts the openapi-fetch response union type which has optional data/error.
 */
export async function unwrap<T>(
  promise: Promise<{ data?: T | null; response: Response; error?: unknown }>
): Promise<T> {
  try {
    const { data, response, error } = await promise;
    if (!response.ok) {
      if (error && isApiError(error)) {
        // openapi-fetch already parsed the error
        throw error;
      }
      // Fallback: try to parse response body
      let payload: unknown = null;
      try {
        payload = await response.clone().json();
      } catch {
        // No body or invalid JSON
      }
      if (payload) {
        throw ApiError.fromPayload(response.status, payload);
      }
      // 5xx without body -> unknown_error (not internal_server_error)
      if (response.status >= 500) {
        throw new ApiError(
          response.status,
          "unknown_error",
          `Server error: ${response.statusText}`
        );
      }
      // Other status without body
      throw new ApiError(
        response.status,
        DEFAULT_ERROR_CODE,
        response.statusText
      );
    }
    if (data === undefined || data === null) {
      // 2xx with null/undefined data - treat as error
      throw new ApiError(response.status, "unknown_error", "Empty response");
    }
    return data;
  } catch (err) {
    if (isApiError(err)) {
      throw err;
    }
    // Network error (TypeError from fetch) or other unexpected error
    if (err instanceof TypeError && err.message.includes("fetch")) {
      throw new ApiError(0, "network_error", "Network error");
    }
    if (err instanceof Error) {
      throw new ApiError(0, "unknown_error", err.message);
    }
    throw new ApiError(0, "unknown_error", "Unknown error");
  }
}
