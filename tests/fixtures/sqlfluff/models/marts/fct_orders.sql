{{
    config(
        materialized='incremental',
        unique_key='order_id',
        incremental_strategy='merge',
        tags=['marts', 'fact']
    )
}}

WITH orders AS (

    SELECT * FROM {{ ref('stg_orders') }}
    {% if is_incremental() %}
    WHERE order_date >= (SELECT MAX(order_date) FROM {{ this }})
    {% endif %}

),

order_items AS (

    SELECT * FROM {{ ref('stg_order_items') }}

),

customers AS (

    SELECT
        customer_id,
        customer_key
    FROM {{ ref('dim_customers') }}

),

products AS (

    SELECT * FROM {{ ref('stg_products') }}

),

order_details AS (

    SELECT
        oi.order_id,
        COUNT(DISTINCT oi.product_id) AS distinct_product_count,
        SUM(oi.quantity) AS total_quantity,
        SUM(oi.line_total) AS calculated_order_total,
        COLLECT_SET(p.category) AS product_categories
    FROM order_items AS oi
    INNER JOIN products AS p
        ON oi.product_id = p.product_id
    GROUP BY oi.order_id

),

final AS (

    SELECT
        {{ dbt_utils.generate_surrogate_key(['o.order_id']) }} AS order_key,
        o.order_id,
        c.customer_key,
        o.customer_id,
        o.order_date,
        DATE_TRUNC('MONTH', o.order_date) AS order_month,
        DATE_TRUNC('QUARTER', o.order_date) AS order_quarter,
        YEAR(o.order_date) AS order_year,
        o.total_amount,
        o.order_status,
        o.is_completed,
        od.distinct_product_count,
        od.total_quantity,
        od.calculated_order_total,
        SIZE(od.product_categories) AS category_count,
        CASE
            WHEN o.total_amount >= 1000 THEN 'large'
            WHEN o.total_amount >= 200 THEN 'medium'
            ELSE 'small'
        END AS order_size,
        CURRENT_TIMESTAMP() AS dbt_updated_at
    FROM orders AS o
    LEFT JOIN customers AS c
        ON o.customer_id = c.customer_id
    LEFT JOIN order_details AS od
        ON o.order_id = od.order_id

)

SELECT * FROM final
