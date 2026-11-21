import createClient, { type Middleware } from 'openapi-fetch';
import { ApiError, DEFAULT_ERROR_CODE } from './errors';
import type { paths } from './schema';

const errorMiddleware: Middleware = {
  async onResponse({ response }) {
    if (!response.ok) {
      let payload: unknown = null;
      try {
        payload = await response.clone().json();
      } catch {
        throw new ApiError(response.status, DEFAULT_ERROR_CODE, response.statusText);
      }
      throw ApiError.fromPayload(response.status, payload);
    }
    return response;
  },
};

export const apiClient = createClient<paths>({
  baseUrl: '',
});

apiClient.use(errorMiddleware);
