{{
    config(
        materialized='table',
        tags=['intermediate']
    )
}}

WITH customers AS (

    SELECT * FROM {{ ref('stg_customers') }}

),

orders AS (

    SELECT * FROM {{ ref('stg_orders') }}

),

order_items AS (

    SELECT * FROM {{ ref('stg_order_items') }}

),

order_summary AS (

    SELECT
        order_id,
        COUNT(*) AS item_count,
        SUM(line_total) AS calculated_total
    FROM order_items
    GROUP BY order_id

),

customer_orders AS (

    SELECT
        c.customer_id,
        c.full_name,
        c.email,
        c.is_active,
        o.order_id,
        o.order_date,
        o.total_amount,
        o.order_status,
        o.is_completed,
        os.item_count,
        os.calculated_total,
        ROW_NUMBER() OVER (
            PARTITION BY c.customer_id
            ORDER BY o.order_date DESC
        ) AS order_recency_rank
    FROM customers AS c
    INNER JOIN orders AS o
        ON c.customer_id = o.customer_id
    LEFT JOIN order_summary AS os
        ON o.order_id = os.order_id

)

SELECT * FROM customer_orders
