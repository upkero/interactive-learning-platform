# ADR-0012: Generation quota accounting

- Status: Accepted
- Date: 2026-11-17
- Author: ExoLiter
- Affects: Stories 1.6, 1.9, 2.7

## Context

Generation quotas are scoped to billing periods. Concurrent requests must not
overspend the limit. A document can have multiple generation batches in different
periods. Demo parts must obey the same accounting rules as generated parts.

## Options

1. Infer a part's period from the document's latest reservation or creation time:
   ambiguous when multiple batches exist.
2. Store the reservation period on each part: an explicit association independent
   of transaction order, timestamps and document statuses.

## Decision

Choose the second option. `DocumentPartRepository.part_owner` returns the owner
and reservation period; part ownership belongs in the parts repository, not the
ledger repository. `PartDraft` and `PartOwner` require an explicit period or `None`.
The migration backfills existing parts from the document's latest reservation;
the original association cannot be recovered for historical multi-batch data.

- One generated part consumes one generation. The caller reserves all parts
  in the same transaction that creates them; publication records a zero-delta
  charge and an exhausted failed part returns one generation. Fallback widgets
  do not change the charge. The existing stub publication and watchdog path are
  checked by `test_generate_publish_and_watchdog_refund` in
  `backend/tests/integration/services/quota/test_quota_rules.py`; the real
  fallback-widget pipeline belongs to story 2.7 and is not implemented yet.
- The journal belongs to the reservation's period, even if processing finishes
  later or the document has a newer reservation. See
  `test_old_part_refund_ignores_newer_document_reservation` and
  `test_old_reservation_refunded_in_original_period` in
  `backend/tests/integration/services/quota/test_quota_ledger_postgres.py`.
- Totals include exactly one billing period, not a range:
  `test_sum_delta_excludes_other_periods` in the same file.
- `FOR UPDATE` in reserve protects against overspending; the partial unique
  index and SAVEPOINT make duplicate part operations safe. In
  `backend/tests/integration/services/quota/test_quota_races.py`,
  `test_parallel_reserves_never_overspend` checks competing reservations and
  `test_reserve_waits_for_uncommitted_refund` checks that reserve waits until
  a concurrent refund commits. Duplicate operations are covered by
  `test_parallel_refunds_are_recorded_once`, `test_worker_and_watchdog_refund_only_once` and
  `test_duplicate_refund_preserves_outer_transaction` in
  `backend/tests/integration/services/quota/test_quota_ledger_postgres.py`.
- Planning and reading do not reserve anything: see
  `test_generate_publish_and_watchdog_refund` and
  `test_plan_preview_is_stable_and_leaves_the_quota_journal_untouched` in
  `backend/tests/integration/api/test_documents_api.py`.
- Recovery retries do not spend again: see `test_watchdog_retry_does_not_spend_again`.
- Sharing and receiving material do not spend quota: see
  `test_receiving_shared_material_does_not_spend_quota`.
- Demo seeding reserves all parts in the transaction that creates them and
  records a zero-delta charge for the published part. Repeated seeding does not
  reserve again. See `test_seed_dev_is_idempotent`,
  `test_seeded_parts_can_publish_and_watchdog_can_refund` and
  `test_seed_quota_failure_rolls_back_all_demo_data` in
  `backend/tests/integration/seed/test_seed_idempotency.py`.
- Upload, parsing, topic browsing, quizzes, reports, and finishing pending
  widgets do not spend generations. Parsing and pending-widget finishing are
  currently explicit placeholders, not working implementations.
  Stories 1.9 and 2.7 must test the real implementations when they are added.
  Upload, document/topic browsing, quiz attempts and reports are checked by
  `test_upload_browse_quiz_and_report_do_not_spend`.

## Consequences

Legacy parts without a reservation retain a null period; accounting for them is
rejected instead of crediting an unrelated period. New demo parts have reservations,
so publication and terminal recovery can account for them normally. A configured
limit below the demo's required parts rejects the seed and rolls back all demo data.
Real parsing must be tested in Story 1.9, and pending/fallback widgets in Story 2.7.

Unqualified test names above refer to `backend/tests/integration/services/quota/test_quota_rules.py`.
