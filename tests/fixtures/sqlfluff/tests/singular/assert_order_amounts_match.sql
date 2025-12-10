/*
    Singular test to verify order amounts match calculated line totals.
    Tests data integrity between orders and order_items.
*/

WITH order_calculated_totals AS (

    SELECT
        order_id,
        SUM(line_total) AS calculated_total
    FROM {{ ref('stg_order_items') }}
    GROUP BY order_id

),

order_totals AS (

    SELECT
        order_id,
        total_amount
    FROM {{ ref('stg_orders') }}

),

mismatched_orders AS (

    SELECT
        o.order_id,
        o.total_amount AS declared_total,
        c.calculated_total,
        ABS(o.total_amount - c.calculated_total) AS difference
    FROM order_totals AS o
    INNER JOIN order_calculated_totals AS c
        ON o.order_id = c.order_id
    WHERE ABS(o.total_amount - c.calculated_total) > 0.01

)

SELECT * FROM mismatched_orders
