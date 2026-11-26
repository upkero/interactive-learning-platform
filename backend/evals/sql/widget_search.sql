-- Run against a seeded database with:
-- psql -v query_vector='<1024-dimensional vector literal>' -f evals/sql/widget_search.sql
-- Add -v primitive_id=three-frame to inspect the filtered query.
\if :{?query_vector}
\else
    \echo 'Provide a query_vector via psql -v query_vector=...'
    \quit
\endif

BEGIN;
SET LOCAL hnsw.ef_search = 100;
SET LOCAL hnsw.iterative_scan = relaxed_order;
EXPLAIN (ANALYZE, BUFFERS)
WITH nearest AS (
    SELECT d.widget_id, d.id, d.text, d.embedding <=> :'query_vector'::vector AS distance
    FROM widget_descriptions d
    WHERE EXISTS (
        SELECT w.id
        FROM widgets w
        WHERE w.id = d.widget_id AND w.status = 'active'
\if :{?primitive_id}
          AND w.primitive_id = :'primitive_id'
\endif
        OFFSET 0
    )
    ORDER BY distance
    LIMIT 40
), best AS (
    SELECT DISTINCT ON (widget_id) widget_id, text, distance
    FROM nearest
    ORDER BY widget_id, distance, id
)
SELECT widget_id, text, distance FROM best ORDER BY distance, widget_id LIMIT 5;
COMMIT;
