-- Same query as WidgetSearchRepository, for EXPLAIN ANALYZE in psql.
-- The application sets ef_search/iterative_scan and the limit in code.
BEGIN;
SET LOCAL hnsw.ef_search = 100;
SET LOCAL hnsw.iterative_scan = relaxed_order;
WITH nearest AS (
    SELECT d.widget_id, d.text, d.embedding <=> :query_vector AS distance
    FROM widget_descriptions d
    JOIN widgets w ON w.id = d.widget_id
    WHERE w.status = 'active'
      AND (:primitive_id IS NULL OR w.primitive_id = :primitive_id)
    ORDER BY d.embedding <=> :query_vector
    LIMIT 40
), best AS (
    SELECT DISTINCT ON (widget_id) widget_id, text, distance
    FROM nearest
    ORDER BY widget_id, distance
)
SELECT widget_id, text, distance FROM best ORDER BY distance LIMIT 5;
COMMIT;
