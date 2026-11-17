# ADR-0012: Generation quota accounting

## Decision

- One generated part consumes one generation. The caller reserves all parts
  in the same transaction that creates them; publication records a zero-delta
  charge and an exhausted failed part returns one generation. Fallback widgets
  do not change the charge. The existing stub publication and watchdog path are
  checked by `test_generate_publish_and_watchdog_refund` in
  `backend/tests/integration/services/quota/test_quota_rules.py`; the real
  fallback-widget pipeline belongs to story 2.7 and is not implemented yet.
- The journal belongs to the reservation's period, even if processing finishes
  later. See `test_old_reservation_refunded_in_original_period` in
  `backend/tests/integration/services/quota/test_quota_ledger.py`.
- Concurrent reserves, refunds, and their combination are serialized by the
  user row lock. See the three tests in
  `backend/tests/integration/services/quota/test_quota_races.py`; duplicate
  refunds use a savepoint, tested by `test_duplicate_refund_preserves_outer_transaction`.
- Planning and reading do not reserve anything: see
  `test_generate_publish_and_watchdog_refund` and
  `test_plan_preview_is_stable_and_leaves_the_quota_journal_untouched` in
  `backend/tests/integration/api/test_documents_api.py`.
- Recovery retries do not spend again: see `test_watchdog_retry_does_not_spend_again`.
- Sharing and receiving material do not spend quota: see
  `test_receiving_shared_material_does_not_spend_quota`.
- Upload, parsing, topic browsing, quizzes, reports, and finishing pending
  widgets do not spend generations. Parsing and pending-widget finishing are
  currently explicit placeholders, not working implementations; their current
  no-write behavior is checked by `test_unimplemented_parser_and_pending_finisher_do_not_spend`.
  Stories 1.9 and 2.7 must test the real implementations when they are added.
  Upload, document/topic browsing, quiz attempts and reports are checked by
  `test_upload_browse_quiz_and_report_do_not_spend`. The complete parser and
  pending-widget finisher must be checked when those features are implemented.

Unqualified test names above refer to `backend/tests/integration/services/quota/test_quota_rules.py`.
