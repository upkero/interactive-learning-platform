import { getRequestConfig } from 'next-intl/server';
import { defaultLocale, locales, type Locale } from './config';
import en from './messages/en.json';
import ru from './messages/ru.json';

const messagesByLocale: Record<Locale, typeof ru> = { ru, en };

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale: Locale = locales.includes(requested as Locale) ? (requested as Locale) : defaultLocale;

  return {
    locale,
    messages: messagesByLocale[locale],
  };
});
