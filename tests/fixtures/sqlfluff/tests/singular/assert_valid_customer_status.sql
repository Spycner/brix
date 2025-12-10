/*
    Singular test to validate customer status values.
    Demonstrates standalone test file patterns for SQLFluff.

    This test fails if any customers have an invalid status value.
*/

SELECT
    customer_id,
    status,
    'Invalid status value' AS failure_reason
FROM {{ ref('stg_customers') }}
WHERE
    status NOT IN ('active', 'inactive', 'churned')
    OR status IS NULL
