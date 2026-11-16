# ADR-0011: Deterministic Celery Redis queue order

## Context

Workers consume `maintenance,parts.high,parts` in that order. Kombu 5.6's
Redis transport exposes active queues as a set. Consequently even its
`priority` strategy cannot guarantee the `-Q` order. The worker must prefer
maintenance and the first part rather than rely on process hash ordering.

## Decision

Keep `queue_order_strategy=priority` and use `OrderedRedisTransport`, whose
channel preserves the consumer registration order. Pin Kombu to 5.6.x because
the adapter relies on its private queue list. A deterministic unit test and a
real Redis/worker integration test must run in CI. Re-evaluate the adapter and
its pin whenever Kombu is upgraded.

## Consequences

Maintenance runs first, then `parts.high`, then `parts`; sustained high-priority
traffic can starve lower-priority work. The adapter is an intentional deviation
from the simple transport configuration, not an implementation of numeric task
priorities. See `backend/docs/architecture.md` for recovery and time limits.
