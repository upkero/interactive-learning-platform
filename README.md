# Grasp — Интерактивная платформа обучения

Grasp превращает учебные материалы (PDF, DOCX, Markdown, Google Docs) в интерактивные конспекты с визуализацией и тестовыми заданиями.

## Быстрый старт для разработки

### 1. Подготовка окружения

Скопируйте шаблон переменных окружения один раз перед первым запуском:

```bash
cp backend/.env.example backend/.env
```

### 2. Запуск проекта

```bash
docker compose -f infra/compose.yml up -d
```

### 3. Запуск с локальной моделью (профиль local-llm)

Чтобы работать без платного ключа Anthropic, поднимите локальную Ollama вместе со стеком:

```bash
docker compose -f infra/compose.yml --profile local-llm up -d
```

## Проверка, что всё поднялось

```bash
docker compose -f infra/compose.yml ps
```

Readiness-проверка API (БД, Redis, MinIO):

```bash
curl http://localhost:8000/health/ready
```

Swagger / OpenAPI-документация доступна в браузере:

```text
http://localhost:8000/docs
```

## Production deployment на VPS

Боевая конфигурация описана в `docs/adr/0009-deployment.md`.

Один раз перед первым деплоем:

```bash
# Пакеты в GHCR приватные по умолчанию
docker login ghcr.io
```

Обновление стека (тег — sha коммита, который CI опубликовал в GHCR):

```bash
# на VPS, из репозитория
IMAGE_TAG=<commit-sha> ./infra/deploy.sh
```

Скрипт требует `IMAGE_TAG` (деплой воспроизводим, без туманных тегов), проверяет `backend/.env` (права 600), тянет образы из GHCR и поднимает стек с Nginx-прокси (порты 80/443).
