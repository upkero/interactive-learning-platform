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

Образ MinIO лежит в **приватном** GHCR-пакете `aistor-minio`, поэтому
перед первым `docker compose up` разово войдите в ghcr.io (токену
достаточно scope `read:packages`):

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

## Демо готового материала

Демо-заполнение создаёт готовый конспект и тест в локальной БД. Воркер
разбирает новые документы после загрузки.
Генерация и обращения к LLM при просмотре конспекта и проверке ответа не нужны.

```bash
docker compose --env-file backend/.env -f infra/compose.yml up -d api worker
docker compose --env-file backend/.env -f infra/compose.yml --profile seed run --rm seed
pnpm install --frozen-lockfile
pnpm --filter grasp-frontend dev
```

Для запуска фронтенда в Compose достаточно `up -d frontend` с теми же
параметрами `--env-file` и `-f`: Compose дождётся готовности API и воркера.

1. Откройте [страницу входа](http://localhost:3000/ru/login). Войдите как
   `bob@example.com` с паролем из `SEED_PASSWORD` в `backend/.env`
   (в шаблоне `dev-seed-password`).
2. В «Моих материалах» откройте **Neural networks basics**. В конспекте
   появится часть **From neurons to layers**.
3. Нажмите «Пройти тест по части», выберите **Activation** и нажмите
   «Завершить тест». На экране появятся результат **1 из 1**, **100%**
   и пояснение. «Вернуться к конспекту» открывает тот же материал.
4. Чтобы проверить загрузку, выберите «Загрузить материал», добавьте
   `backend/tests/fixtures/documents/course_en.md` и нажмите «Импортировать».
   После разбора откроется список тем. Для этого файла разбор обходится без LLM.

## Проверка, что всё поднялось

```bash
docker compose --env-file backend/.env -f infra/compose.yml ps
```

Если импорт остаётся в очереди, проверьте статус `worker` и его журнал:
`docker compose --env-file backend/.env -f infra/compose.yml logs --tail=100 worker`.
При старте воркер выводит список очередей, в котором должна быть `parts.high`.

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

Настройте DNS для четырёх имён: `app.<домен>` (приложение и API на `/api/`),
`widgets.<домен>` (iframe-виджеты), `files.<домен>` (MinIO) и
`grafana.<домен>` (Grafana). Удалите старую
DNS-запись отдельного домена API. Например, список имён сертификата:

```bash
certbot certonly --webroot -w /var/www/certbot --cert-name grasp.example \
  -d app.grasp.example -d widgets.grasp.example -d files.grasp.example -d grafana.grasp.example
```

При реализации frontend (4.1.1) адрес назначения server-side rewrites для
`/api/:path*` должен читаться из `API_INTERNAL_URL`: на хосте по умолчанию
`http://localhost:8000`, в Compose — `http://api:8000` (см. `frontend/.env.example`).

Один раз перед первым деплоем — пакет MinIO в GHCR приватный, без
входа VPS не скачает образ:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u <github-логин> --password-stdin
```

Обновление стека (тег — sha коммита, который CI опубликовал в GHCR):

```bash
# на VPS, из репозитория
IMAGE_TAG=<commit-sha> ./infra/deploy.sh
```

Скрипт требует `IMAGE_TAG` (деплой воспроизводим, без туманных тегов), проверяет `backend/.env` (права 600) и XFS-каталог `MINIO_DATA_DIR`, тянет образы из GHCR и поднимает стек с Nginx-прокси (порты 80/443). Пакет `aistor-minio` приватный — без `docker login ghcr.io` на самой VPS деплой не скачает образ MinIO.
# Наблюдаемость

Для локального Compose задайте `GF_SECURITY_ADMIN_PASSWORD` в `backend/.env`.
Grafana доступна только с локального компьютера на `http://127.0.0.1:3001`,
Prometheus — на `http://127.0.0.1:9090`. Вход в Grafana: пользователь `admin`
и заданный пароль. Production требует отдельный сильный пароль и TLS-домен
`grafana.<домен>` в сертификате; в `backend/.env` задайте также
`GF_SERVER_ROOT_URL=https://grafana.<домен>/` с вашим доменом. Этот адрес должен
совпадать с именем в конфигурации Nginx и сертификате. Внутренние порты наружу
не публикуются.

Для отчёта выгрузите журнал и запустите скрипт из `backend/`:

```sh
logcli --addr=http://127.0.0.1:3100 query '{logger="grasp.decisions"} | json | event="part.summary"' --output=jsonl --limit=10000 > parts.jsonl
uv run python evals/usage_report.py parts.jsonl parts.csv
```

Доля кэша — `cache_read / (input + cache_read + cache_write)`. Если цена
модели неизвестна, стоимость части остаётся пустой, а не считается нулевой.
Для локального Celery с пулом prefork (даже с одним процессом) задайте `PROMETHEUS_MULTIPROC_DIR`
как существующий доступный на запись каталог и очищайте его перед стартом.
