# Grasp — Контекст курсового проекта и задачи 1.1 (SCRUM-6)

## 1. О проекте Grasp

Grasp — интерактивная платформа адаптивного обучения. Пользователь загружает учебный документ (PDF, DOCX, Markdown, ссылка на Google Docs), система анализирует его структуру, делит на смысловые темы (~15k токенов на часть), а языковая модель (Claude / локальная Ollama) генерирует интерактивный конспект:

1. Упрощённый текст с сохранением ключевой терминологии.
2. Картинки и схемы, извлеченные из оригинала.
3. Интерактивные визуализации/виджеты двух типов:
   - _виджеты-конфиги_ (на базе React-примитивов из `@grasp/primitives`);
   - _виджеты-код_ (сгенерированные моделью компоненты, изолированные в iframe на домене `widgets.<домен>`).
4. Проверенные тестовые задания (квизы) для самопроверки.

## 2. Команда и разделение ролей

- **Илья (ExoLiter, автор данного контекста):** Бэкенд / DevOps — **Эпик 1: Платформа и данные** (инфраструктура, Docker Compose, CI, БД PostgreSQL 17 + pgvector, MinIO S3, Celery очереди, квоты, наблюдаемость, песочница).
- **Дима:** AI-инженер — **Эпик 2: Решатель** (промпты, клиенты LLM, агентные цепочки, синтез виджетов, квизы).
- **Рома:** Фронтенд / Визуализация — **Эпик 3: Библиотека визуализаций** (`primitives/`).
- **Андрей:** Фронтенд / Приложение — **Эпик 4: Клиентское приложение** (`frontend/`, `widget-host/`).
- **Тимлид:** Архитектура, ревью сквозных PR, ведение ADR.

## 3. Текущее состояние репозитория и Git Flow

- **Репозиторий:** `https://github.com/upkero/interactive-learning-platform`
- **Целевая ветка разработки:** `dev` (все PR открываются в `dev`!).
- **Текущая рабочая ветка:** `feat/SCRUM-6-platform-setup`.
- **Открытый Pull Request:** PR #1 (`feat/SCRUM-6-platform-setup` -> `dev`).
- **Формат коммитов:** Conventional Commits (`feat(scope): message (SCRUM-N)`).

## 4. Задача 1.1 (SCRUM-6): «Окружение и развёртывание»

Содержит 5 подзадач:

- `1.1.1 (SCRUM-7)` — Монорепо, линтеры (Ruff, Mypy strict), pre-commit, pnpm workspace.
- `1.1.2 (SCRUM-8)` — Docker Compose (все 10+ сервисов стека), multi-stage `backend/Dockerfile`.
- `1.1.3 (SCRUM-9)` — CI в GitHub Actions (`.github/workflows/ci.yml` с 5 джобами).
- `1.1.4 (SCRUM-10)` — Pydantic `BaseSettings` (`core/settings/`), `.env.example`, `docs/adr/0008-config-and-secrets.md`.
- `1.1.5 (SCRUM-11)` — Конфиги для VPS: `infra/nginx/grasp.conf`, `infra/compose.prod.yml`, `infra/deploy.sh`, `docs/adr/0009-deployment.md`.

---

## 5. Замечания второго ревью тимлида к PR #1 (План исправлений)

### Блокер 1: Файлы для VPS (1.1.5) отсутствуют в ветке

Необходимо создать/добавить:

1. `infra/compose.prod.yml`:
   - Сервис `nginx` (порты `80:80`, `443:443`, монтирование `/etc/letsencrypt` и `/var/www/certbot:ro`).
   - Сброс наружных портов у внутренних сервисов: `ports: !reset []` у `db`, `redis`, `minio`, `api`, `frontend`, `widget-host`.
   - `restart: unless-stopped` для всех сервисов.
   - Использование `image: ghcr.io/<repo>/<service>:${IMAGE_TAG:-latest}`.
2. `infra/nginx/grasp.conf`:
   - Маршрутизация по 4 поддоменам (`app`, `api`, `widgets`, `files`).
   - Редирект `80 -> 443`, поддержка ACME-challenge (`/.well-known/acme-challenge/`).
   - Закрытие `/metrics` снаружи (`deny all;`).
   - Для SSE `/api/v1/documents/*/events`: `proxy_buffering off; proxy_read_timeout 1h;`.
   - Для `files.<домен>`: `proxy_set_header Host $host` (важно для проверки подписи presigned S3).
   - Лимит тела запроса: `client_max_body_size 55m;`.
   - Проброс заголовков `X-Request-ID`, `X-Forwarded-*`.
3. `infra/deploy.sh`:
   - `chmod 600 backend/.env`.
   - `docker compose -f infra/compose.yml -f infra/compose.prod.yml pull && ... up -d --remove-orphans`.
4. `docs/adr/0009-deployment.md`:
   - Фиксация архитектуры: 4 vCPU / 8 GB RAM, Nginx reverse proxy, certbot webroot на хосте, UFW закрывает всё, кроме 22/80/443.

### Блокер 2: `.env.example` и адреса для Docker Compose

Критерий задачи: `cp backend/.env.example backend/.env && docker compose up -d` должен поднимать рабочий стек.

- Проблема: если в `.env.example` указан `localhost`, контейнеры внутри Compose пытаются стучаться сами в себя и падают (`Connection refused`).
- Решение: В `backend/.env.example` по умолчанию выставить адреса для Docker Compose (`db:5432`, `redis:6379/0`, `http://minio:9000`, `http://ollama:11434/v1`), а в комментариях явно указать: `Для локального запуска вне Docker замените имя сервиса на localhost`.

### Блокер 3: Эндпоинт `/health/ready`

Критерий задачи: `/health/ready` возвращает 200.

- В шаблоне `ready` зависел от LLM, а без поднятой Ollama возвращал 503.
- По правилам Grasp (раздел 1.4.1): `/health/ready` проверяет доступность БД (SELECT 1), Redis (PING) и MinIO (ping()), **но не языковую модель** (недоступность Anthropic/Ollama не делает API неготовым). Убрать пинг LLM из readiness check!

### Блокер 4: Healthcheck в Docker Compose

1. **`worker` и `beat`:** наследуют `HEALTHCHECK` из `backend/Dockerfile`, где прописан `curl localhost:8000/health/live`. Но в них нет веб-сервера!
   - В `infra/compose.yml` для `beat` и `migrate` переопределить: `healthcheck: { disable: true }`.
   - Для `worker` сделать проверку через Celery: `healthcheck: { test: ["CMD-SHELL", "celery -A src.worker inspect ping || exit 1"], interval: 15s, retries: 5 }`.
2. **`minio`:** современные образы MinIO не имеют утилиты `curl`.
   - Использовать `healthcheck: { test: ["CMD-SHELL", "mc ready local || curl -f http://localhost:9000/minio/health/live || exit 1"], interval: 10s, retries: 10 }`.

### Блокер 5: Ошибки в `README.md`

- Исправить опечатку `up -d0` -> `up -d`.
- Закрыть незакрытые блоки кода Markdown (```).
- Убрать дублирование `cp backend/.env.example backend/.env`.
- Добавить раздел о проверке (`docker compose ps`, `/health/ready`, `/docs`) и о запуске с профилем `--profile local-llm`.

### Блокер 6: Описание и заголовок PR #1

- Заголовок PR: `feat(infra): platform setup, compose, ci, settings and vps deployment (SCRUM-6)`.
- Описание должно точно перечислять реально созданные файлы и настройки, без приписок того, чего нет.

### Мелочи:

- Удалить UTF-8 BOM во всех файлах (особенно `.ini`, `.json`, `Dockerfile`). Сохранять в чистом UTF-8 (no BOM).
- Убедиться, что в конце каждого текстового файла есть символ новой строки `\n` (`end-of-file-fixer`).
- Проверить, что `pre-commit run --all-files` проходит без ошибок.
- Проверить, что `uv run mypy src` проходит в strict-режиме (50+ файлов).
- Проверить, что `uv run pytest -m "unit or integration"` успешен.
