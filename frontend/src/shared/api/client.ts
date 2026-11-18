import createClient, { type Middleware } from 'openapi-fetch';
import { ApiError } from './errors';
import type { paths } from './schema';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const errorMiddleware: Middleware = {
  async onResponse({ response }) {
    if (!response.ok) {
      let payload: unknown = null;
      try {
        payload = await response.clone().json();
      } catch {
        throw new ApiError(response.status, 'unknown_error', response.statusText);
      }
      throw ApiError.fromPayload(response.status, payload);
    }
    return response;
  },
};

export const apiClient = createClient<paths>({
  baseUrl: API_BASE_URL,
  credentials: 'include',
});

apiClient.use(errorMiddleware);
