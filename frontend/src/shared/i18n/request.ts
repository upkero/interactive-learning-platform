import { hasLocale } from "next-intl";
import { getRequestConfig } from "next-intl/server";
import { defaultLocale, locales, type Locale } from "./config";
import en from "./messages/en.json";
import ru from "./messages/ru.json";

const messagesByLocale: Record<Locale, typeof ru> = { ru, en };

export default getRequestConfig(async (params) => {
  // eslint-disable-next-line @typescript-eslint/no-deprecated -- Next 15 has no next/root-params.
  const { requestLocale } = params;
  const requestedLocale = await requestLocale;
  const locale = hasLocale(locales, requestedLocale)
    ? requestedLocale
    : defaultLocale;

  return {
    locale,
    messages: messagesByLocale[locale],
  };
});
