Проект Grasp, frontend/: Next.js 15 (App Router), TypeScript strict, TanStack Query, openapi-fetch, next-intl (ru/en, localePrefix always), zod, Vitest, Playwright.
Слои src/: app → features → entities → shared; импорты только сверху вниз, фичи не импортируют друг друга, импорт фичи/сущности только через index.ts.
Правила:
— типы API только из shared/api/schema.d.ts (генерируется pnpm api:gen), руками не писать;
— fetch к API только в shared/api; компоненты не вызывают apiClient, только хуки из api.ts;
— ключи кэша только из qk; после мутаций инвалидировать конкретные ключи;
— Link/useRouter/redirect только из @/shared/i18n/navigation;
— все строки через useTranslations, русских литералов в JSX нет;
— тексты ошибок только из errors.<error_code>;
— 'use client' на листовых компонентах, данные грузятся на клиенте;
— rehype-raw и dangerouslySetInnerHTML запрещены;
— цвета только из токенов, у интерактивных элементов видимый :focus-visible;
— у каждого запроса три состояния: скелетон, пусто (с действием), ошибка (текст + «Повторить»).
