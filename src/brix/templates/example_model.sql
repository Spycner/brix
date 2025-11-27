-- This is an example dbt model
-- Models are SELECT statements that dbt materializes as views or tables
-- Delete this file once you've created your own models

SELECT
    1 AS id,
    'hello' AS message,
    CURRENT_TIMESTAMP AS created_at
