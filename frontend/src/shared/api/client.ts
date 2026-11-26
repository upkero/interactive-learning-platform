import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";

const localeMiddleware: Middleware = {
  onRequest({ request }) {
    // Get locale from cookie or default to 'ru'
    // In browser, we can read from document.cookie; on server, from headers
    let locale = "ru";
    if (typeof document !== "undefined") {
      const cookies = document.cookie
        .split("; ")
        .reduce<Record<string, string>>((acc, cookie) => {
          const [key, value] = cookie.split("=");
          acc[key] = value;
          return acc;
        }, {});
      locale = cookies["locale"] || cookies["NEXT_LOCALE"] || "ru";
    }
    request.headers.set("Accept-Language", locale);
    return request;
  },
};

const errorMiddleware: Middleware = {
  async onResponse({ response }) {
    if (!response.ok) {
      let payload: unknown = null;
      try {
        payload = await response.clone().json();
      } catch {
        // No body or invalid JSON
      }
      if (payload) {
        // The error will be thrown by unwrap() based on the payload
        return response;
      }
      // For 5xx without body, unwrap() will convert to 'unknown_error'
      return response;
    }
    return response;
  },
};

export const apiClient = createClient<paths>({
  baseUrl: "",
});

apiClient.use(localeMiddleware);
apiClient.use(errorMiddleware);
