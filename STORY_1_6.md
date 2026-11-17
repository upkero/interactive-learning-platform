## 1.6 Квоты генераций

Исполнитель: Бэкенд/DevOps · Метки: Backend, QA · Зависит от: 1.2 База данных PostgreSQL · Блокирует: 1.4.6, 1.4.7, 2.7 Оркестрация части

### Зачем
Каждая часть стоит денег: основной проход, резолвер, синтез и задания — это десятки тысяч токенов. Поэтому у пользователя есть месячный лимит генераций (по умолчанию 20), одна генерация — одна часть. Лимит должен быть точным при параллельных запусках: два одновременных generate не могут вместе потратить больше, чем осталось. И честным: если часть упала, генерация возвращается.

Остаток не хранится счётчиком в users. Вместо этого есть журнал generation_ledger, где каждая операция — строка с delta. Журнал отвечает на вопросы «куда ушли генерации» и «почему вернулись», его легко проверять в тестах и нельзя испортить потерянным обновлением.

### Где в коде

| Что | Путь |
| --- | --- |
| Журнал квот (сервис) | backend/src/app/services/quota/quota_ledger.py |
| Расчёт периода | backend/src/app/services/quota/period.py |
| Репозитории | backend/src/app/repositories/generation_ledger_repository.py, backend/src/app/repositories/user_repository.py |
| Контракты | backend/src/app/contracts/quota/{quota_state,ledger_entry,period}.py |
| Исключения | backend/src/app/exceptions/quota.py |
| Настройки | backend/src/app/core/settings/quota.py |
| Тесты гонок | backend/tests/integration/services/quota/test_quota_races.py |

### Как устроено

Рисунок 5 — Операции с квотой

На диаграмме три операции и одна формула. Остаток: available = monthly_limit + Σdelta по записям пользователя за текущий период. reserve пишет delta = −n при запуске генерации на n частей — генерации уходят сразу, ещё до обработки. charge пишет delta = 0 при публикации части: остаток не меняется, запись фиксирует факт, что часть действительно потрачена. refund пишет delta = +1, когда часть окончательно упала. Важно, что все три операции идут в транзакции с SELECT … FOR UPDATE по строке users: пока одна транзакция считает остаток и пишет reserve, вторая ждёт на блокировке и потом видит уже новую сумму.

QuotaLedger принимает AsyncSession параметром и сам не коммитит. Так резерв попадает в ту же транзакцию, что и создание частей (1.4.7), а возврат — в ту же, что и перевод части в failed (1.5.3). Если транзакция откатится, откатятся и части, и запись журнала.

Период. Если у пользователя period_anchor пуст — календарный месяц, с 1-го числа. Если задан (дата оплаты) — период начинается в день месяца, равный дню якоря; для коротких месяцев день обрезается до последнего (якорь 31-го → 30 апреля, 28 или 29 февраля). Начало периода пишется в каждую запись журнала (period_start), поэтому сумма считается по индексу (user_id, period_start) без диапазонов дат.

> **Решение:** QuotaLedger принимает сессию снаружи (reserve(session, …), charge(session, …), refund(session, …)), а не открывает свою, — иначе резерв и создание частей не будут атомарны.

> **Решение:** refund и charge пишутся в период исходного резерва, сохранённый в `document_parts.quota_period_start` при создании части. Последний резерв документа выбирать нельзя: у документа может быть несколько запусков в разных периодах. Иначе часть, упавшая 1-го числа, подарит пользователю лишнюю генерацию в новом месяце.

> **Решение:** что тратит генерацию: только запуск части через generate (одна часть — одна генерация). Не тратят: загрузку, разбор, дерево тем, plan, просмотр, задания, жалобы, получение материала от другого пользователя, перезапуск сторожем, догенерацию pending-виджетов. Упавшая часть возвращает генерацию; часть, опубликованная с fallback-виджетами, — нет.

Документация: PostgreSQL: явные блокировки, SQLAlchemy: with_for_update.

### Правила
• Все записи в generation_ledger — только через QuotaLedger. Репозиторий журнала сервисы напрямую не используют.
• Каждая операция QuotaLedger начинается с UserRepository.lock_for_update(user_id). Повторная блокировка той же строки в той же транзакции безопасна.
• QuotaLedger не коммитит и не открывает сессий; вызывающий обязан вызывать его внутри session.begin().
• charge и refund для одной части — не больше одной записи каждого вида (частичный уникальный индекс); повторный вызов ловит IntegrityError и считается успешным no-op.
• Дата «сегодня» приходит из инжектируемых часов Clock (UTC), а не из date.today() внутри логики — иначе тесты периодов не написать.
• Нехватка квоты — QuotaExceededError (402, error_code="quota_exceeded") с available и requested в extra.
• В тестах на гонки используем настоящий Postgres: фейк в памяти не воспроизводит блокировки.

### Пример кода

Расчёт периода:
```python
# backend/src/app/services/quota/period.py
import calendar
from datetime import date

from src.app.contracts.quota import QuotaPeriod  # end — исключительная граница

def _clamped(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))

def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1

def current_period(today: date, anchor: date | None) -> QuotaPeriod:
    day = 1 if anchor is None else anchor.day
    start = _clamped(today.year, today.month, day)
    if start > today: # день якоря в этом месяце ещё не наступил
        y, m = _shift_month(today.year, today.month, -1)
        start = _clamped(y, m, day)
    y, m = _shift_month(start.year, start.month, 1)
    return QuotaPeriod(start=start, end=_clamped(y, m, day))
```

Журнал квот:
```python
# backend/src/app/services/quota/quota_ledger.py
class QuotaLedger:
    def __init__(self, *, users_factory: Callable[[AsyncSession], UserRepository],
                 ledger_factory: Callable[[AsyncSession], GenerationLedgerRepository],
                 parts_factory: Callable[[AsyncSession], DocumentPartRepository], clock: Clock) -> None:
        self._users = users_factory
        self._ledger = ledger_factory
        self._parts = parts_factory
        self._clock = clock

    async def available(self, session: AsyncSession, *, user_id: UUID) -> QuotaState:
        user = await self._users(session).get_quota_fields(user_id)
        return await self._state(session, user)

    async def reserve(self, session: AsyncSession, *, user_id: UUID, document_id: UUID, parts: int) -> QuotaState:
        user = await self._users(session).lock_for_update(user_id) # SELECT … FROM users WHERE id=:id FOR UPDATE
        state = await self._state(session, user)
        if parts > state.available:
            raise QuotaExceededError(extra={"available": state.available, "requested": parts})
        await self._ledger(session).add(
            user_id=user_id, document_id=document_id, part_id=None,
            op=LedgerOp.RESERVE, delta=-parts, period_start=state.period.start,
        )
        return replace(state, available=state.available - parts)

    async def charge(self, session: AsyncSession, *, part_id: UUID) -> None:
        await self._write_for_part(session, part_id, LedgerOp.CHARGE, delta=0)

    async def refund(self, session: AsyncSession, *, part_id: UUID) -> None:
        await self._write_for_part(session, part_id, LedgerOp.REFUND, delta=+1)

    async def _write_for_part(self, session: AsyncSession, part_id: UUID, op: LedgerOp, *, delta: int) -> None:
        ledger = self._ledger(session)
        owner = await self._parts(session).part_owner(part_id) # владелец и период части
        await self._users(session).lock_for_update(owner.user_id)
        period_start = owner.quota_period_start
        if period_start is None:
            raise QuotaReservationNotFoundError()
        try:
            async with session.begin_nested(): # SAVEPOINT: дубль не рушит внешнюю транзакцию
                await ledger.add(user_id=owner.user_id, document_id=owner.document_id, part_id=part_id,
                                 op=op, delta=delta, period_start=period_start)
        except LedgerEntryDuplicateError:
            return # уже записано — идемпотентно

    async def _state(self, session: AsyncSession, user: UserQuotaFields) -> QuotaState:
        period = current_period(self._clock.today(), user.period_anchor)
        spent = await self._ledger(session).sum_delta(user.id, period.start) # COALESCE(SUM(delta), 0)
        return QuotaState(monthly_limit=user.monthly_limit, available=user.monthly_limit + spent, period=period)
```

Блокировка строки пользователя:
```python
# backend/src/app/repositories/user_repository.py
async def lock_for_update(self, user_id: UUID) -> UserQuotaFields:
    stmt = (
        select(User.id, User.monthly_limit, User.period_anchor)
        .where(User.id == user_id)
        .with_for_update()
    )
    row = (await self._session.execute(stmt)).one_or_none()
    if row is None:
        raise UserNotFoundError()
    return UserQuotaFields(id=row.id, monthly_limit=row.monthly_limit, period_anchor=row.period_anchor)
```

Тест на гонку:
```python
# backend/tests/integration/services/quota/test_quota_races.py
@pytest.mark.integration
async def test_parallel_reserves_never_overspend(container: ApplicationContainer, user_id: UUID,
                                                 document_ids: list[UUID]) -> None:
    ledger = container.quota_ledger # monthly_limit = 20, журнал пуст

    async def attempt(document_id: UUID) -> bool:
        async with container.session_factory() as session, session.begin():
            try:
                await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=5)
                return True
            except QuotaExceededError:
                return False

    results = await asyncio.gather(*(attempt(d) for d in document_ids[:6]))
    assert sum(results) == 4
    async with container.session_factory() as session:
        state = await ledger.available(session, user_id=user_id)
        assert state.available == 0
```

### Критерии приёмки
• Шесть параллельных reserve по 5 при лимите 20 дают ровно 4 успеха и остаток 0; тест проходит 50 прогонов подряд без флаков.
• Параллельные refund для одной части (сторож и задача) дают одну запись +1; остаток растёт на 1.
• current_period покрыт таблицей случаев: без якоря; якорь 31-го в феврале високосного и обычного года; якорь 15-го до и после 15-го; переход через Новый год.
• Сквозной сценарий: generate на 3 части → одна часть failed сторожем → GET /me/quota показывает limit − 2; в журнале reserve −3, charge 0 ×2, refund +1.
• Пользователь с period_anchor видит в GET /me/quota правильные period_start и period_end.

---

### Подзадачи

#### 1.6.1 Журнал операций: резерв, списание, возврат с блокировкой строки
Исполнитель: Бэкенд/DevOps · Метка: Backend

Написать QuotaLedger с методами available, reserve, charge, refund: сессия снаружи, блокировка users через lock_for_update, запись через GenerationLedgerRepository.add, идемпотентность charge/refund через SAVEPOINT и уникальный индекс. Репозиторий журнала предоставляет add и sum_delta; part_owner — репозиторий частей. Зарегистрировать сервис в контейнере; charge вызывает конвейер 2.7 при публикации, refund — PartRecovery.

Файлы: services/quota/quota_ledger.py, repositories/generation_ledger_repository.py, repositories/user_repository.py, contracts/quota/*.py, exceptions/quota.py, bootstrap/container.py.

Готово, когда: юнит-тесты на фейках покрывают все операции; интеграционный тест подтверждает, что повторный refund не создаёт вторую запись и не откатывает внешнюю транзакцию.

#### 1.6.2 Расчёт остатка и периода
Исполнитель: Бэкенд/DevOps · Метка: Backend

Написать current_period(today, anchor) с обрезкой дня до конца короткого месяца и контракт QuotaPeriod. Ввести интерфейс Clock (today() в UTC) с системной реализацией и фейком для тестов. QuotaSettings — QUOTA_DEFAULT_MONTHLY_LIMIT=20 (для новых пользователей). Подключить результат к GET /me/quota и к plan (1.4.6).

Файлы: services/quota/period.py, contracts/quota/period.py, core/clock.py, core/settings/quota.py, tests/unit/services/quota/test_period.py.

Готово, когда: параметризованный тест на 12+ датах проходит, включая 29 февраля и 31 декабря; GET /me/quota отдаёт те же границы.

#### 1.6.3 Правила расхода и тесты на гонки
Исполнитель: Бэкенд/DevOps · Метка: QA

Зафиксировать правила расхода из этой истории в docs/adr/NNNN-quota-rules.md и проверить каждое тестом: plan, разбор, перезапуск сторожем, finish_pending_widgets, получение материала — не меняют остаток; падение части возвращает одну генерацию. Написать интеграционные тесты на гонки: параллельные reserve, параллельные refund, reserve параллельно с refund. Запускать их в CI с pytest --count=20 (pytest-repeat).

Файлы: tests/integration/services/quota/test_quota_races.py, tests/integration/services/quota/test_quota_rules.py, docs/adr/NNNN-quota-rules.md.

Готово, когда: все тесты стабильно проходят в CI 20 раз подряд; каждый пункт ADR ссылается на свой тест.
```
