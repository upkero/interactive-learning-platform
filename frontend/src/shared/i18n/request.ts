import { getRequestConfig } from 'next-intl/server';
import { defaultLocale, locales, type Locale } from './config';
import en from './messages/en.json';
import ru from './messages/ru.json';

const messagesByLocale: Record<Locale, typeof ru> = { ru, en };

export default getRequestConfig(({ locale }) => {
  const validLocale: Locale = locales.includes(locale as Locale) ? (locale as Locale) : defaultLocale;

  return {
    locale: validLocale,
    messages: messagesByLocale[validLocale],
  };
});
