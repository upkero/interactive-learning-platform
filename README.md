# Grasp — Интерактивная платформа обучения

Grasp превращает учебные материалы (PDF, DOCX, Markdown, Google Docs) в интерактивные конспекты с визуализацией и тестовыми заданиями.

## Быстрый старт для разработки

### 1. Подготовка окружения

Скопируйте шаблон переменных окружения один раз перед первым запуском:

```bash
cp backend/.env.example backend/.env
```

### 2. Запуск проекта

Все команды compose запускаются с `--env-file backend/.env`: секция
`env_file` подставляет переменные в контейнеры, но на интерполяцию
самого compose (например, `MINIO_DATA_DIR`) она не влияет.

```bash
docker compose --env-file backend/.env -f infra/compose.yml up -d
```

Образ MinIO лежит в GHCR-пакете `aistor-minio`; если лид перевёл его в
Private, разово войдите в ghcr.io (токену достаточно scope `read:packages`):

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u <github-логин> --password-stdin
```

Данные MinIO лежат на XFS-каталоге из `MINIO_DATA_DIR` — разовая
настройка диска описана в [docs/minio-xfs.md](docs/minio-xfs.md).

### 3. Запуск с локальной моделью (профиль local-llm)

Чтобы работать без платного ключа Anthropic, поднимите локальную Ollama вместе со стеком:

```bash
docker compose --env-file backend/.env -f infra/compose.yml --profile local-llm up -d
```

## Проверка, что всё поднялось

```bash
docker compose --env-file backend/.env -f infra/compose.yml ps
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

Один раз перед первым деплоем (если образы в GHCR переведены в Private):

```bash
docker login ghcr.io
```

Обновление стека (тег — sha коммита, который CI опубликовал в GHCR):

```bash
# на VPS, из репозитория
IMAGE_TAG=<commit-sha> ./infra/deploy.sh
```

Скрипт требует `IMAGE_TAG` (деплой воспроизводим, без туманных тегов), проверяет `backend/.env` (права 600) и XFS-каталог `MINIO_DATA_DIR`, тянет образы из GHCR и поднимает стек с Nginx-прокси (порты 80/443). Если пакет `aistor-minio` переведён в Private, войдите в GHCR и на самой VPS.
