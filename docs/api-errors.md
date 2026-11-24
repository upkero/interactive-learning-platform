# Ошибки API

Все пути ниже указаны относительно `/api/v1`. Ответ содержит `error_code` и `detail`;
перечисленные дополнительные поля находятся на верхнем уровне ответа, а не внутри `extra`.
Указаны операции, объявляющие соответствующий HTTP-статус в OpenAPI и применимые к причине ошибки.

## Публичные коды

| Код | HTTP | Когда возникает | Поля `extra` | Эндпоинты |
|---|---|---|---|---|
| `request_validation_error` | 422 | Ошибка проверки параметров или тела запроса; `detail` содержит список ошибок | — | Все операции, объявляющие 422 в OpenAPI |
| `not_authenticated` | 401 | Нет действительной сессии | — | Все защищённые операции, объявляющие 401 в OpenAPI |
| `invalid_credentials` | 401 | Неверный email или пароль | — | `POST /auth/login` |
| `email_taken` | 409 | Email уже зарегистрирован | — | `POST /auth/register` |
| `document_not_found` | 404 | Документ отсутствует или недоступен | — | `GET /documents/{document_id}`, `GET /documents/{document_id}/topics`, `POST /documents/{document_id}/plan`, `POST /documents/{document_id}/generate`, `POST /materials/share` |
| `part_not_found` | 404 | Часть отсутствует или недоступна | — | `GET /parts/{part_id}` |
| `quiz_not_found` | 404 | Задание отсутствует или недоступно | — | `POST /quiz-attempts` |
| `document_not_ready` | 409 | Документ ещё не разобран или завершился ошибкой разбора | `status`; для failed также `reason` (`DocumentErrorCode`) | `GET /documents/{document_id}/topics`, `POST /documents/{document_id}/plan`, `POST /documents/{document_id}/generate` |
| `quota_exceeded` | 402 | Недостаточно оставшихся генераций | `available`, `requested` | `POST /documents/{document_id}/generate` |
| `processing_limit_reached` | 429 | Достигнут лимит одновременно обрабатываемых документов | `limit` | `POST /documents`, `POST /documents/import`, `POST /documents/{document_id}/generate` |
| `invalid_gdocs_url` | 422 | Ссылка не указывает на документ Google Docs | — | `POST /documents/import` |
| `empty_topic_selection` | 422 | Темы не выбраны | — | `POST /documents/{document_id}/plan`, `POST /documents/{document_id}/generate` |
| `unknown_topic` | 422 | Выбранная тема отсутствует в документе | — | `POST /documents/{document_id}/plan`, `POST /documents/{document_id}/generate` |
| `recipient_not_registered` | 422 | Получатель не зарегистрирован | — | `POST /materials/share` |
| `file_too_large` | 413 | Размер файла превышает лимит | — | `POST /documents` |
| `unsupported_file_type` | 415 | Тип или содержимое файла не поддерживаются | — | `POST /documents` |
| `too_many_pages` | 422 | В PDF слишком много страниц | — | `POST /documents` |
| `http_error` | Разный | Ошибка HTTP-маршрутизации или инфраструктуры | — | Любой путь; в том числе отсутствующий маршрут |
| `internal_server_error` | 500 | Внутренняя ошибка приложения; подробности клиенту не раскрываются | — | Все операции, объявляющие 500 в OpenAPI |
| `rate_limited` | 429 | Превышен лимит попыток с адреса клиента | — | `POST /auth/register`, `POST /auth/login` |
| `share_with_self` | 422 | Попытка поделиться документом с собой | — | `POST /materials/share` |
| `invalid_quiz_answer` | 422 | Ответ не соответствует типу задания или содержит повторы | — | `POST /quiz-attempts` |
| `widget_not_found` | 404 | Виджет отсутствует или недоступен | — | `POST /widgets/{widget_id}/reports` |
| `queue_unavailable` | 503 | Очередь недоступна после сохранения: upload/import помечают документ failed/enqueue_failed; части generate остаются queued | — | `POST /documents`, `POST /documents/import`, `POST /documents/{document_id}/generate` |

Документ со статусом `failed`, у которого нет `error_code` и сохранено дерево тем,
считается неудачным запуском генерации. Его можно повторно планировать и запускать;
для такого состояния `document_not_ready` не возвращается.

## Коды ошибок документа

Код доступен в `GET /documents/{document_id}` как `error_code`, а при ошибке
`document_not_ready` для документа в состоянии failed — как `reason`.

| Код | Когда возникает | Где видит клиент |
|---|---|---|
| `enqueue_failed` | Задача разбора не поставлена в очередь | `error_code` документа или `reason` ответа 409 |
| `parse_failed` | Ошибка разбора; миграция 0003 также переводит старые тексты ошибок в этот код | То же |
| `too_many_pages` | Превышен предел страниц при разборе (история 1.9) | То же |
| `empty_document` | Документ пуст (история 1.9) | То же |
| `gdocs_not_public` | Google Docs недоступен публично (история 1.9) | То же |
| `gdocs_import_failed` | Не удалось импортировать Google Docs (история 1.9) | То же |
