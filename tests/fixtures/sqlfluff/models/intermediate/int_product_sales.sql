{{
    config(
        materialized='table',
        tags=['intermediate']
    )
}}

{% set price_tiers = ['budget', 'standard', 'premium'] %}

WITH products AS (

    SELECT * FROM {{ ref('stg_products') }}

),

order_items AS (

    SELECT * FROM {{ ref('stg_order_items') }}

),

orders AS (

    SELECT * FROM {{ ref('stg_orders') }}

),

product_sales AS (

    SELECT
        p.product_id,
        p.product_name,
        p.category,
        p.price,
        p.price_tier,
        COUNT(DISTINCT oi.order_id) AS order_count,
        SUM(oi.quantity) AS total_units_sold,
        SUM(oi.line_total) AS total_revenue,
        AVG(oi.line_total) AS avg_order_value,
        MIN(o.order_date) AS first_order_date,
        MAX(o.order_date) AS last_order_date
    FROM products AS p
    LEFT JOIN order_items AS oi
        ON p.product_id = oi.product_id
    LEFT JOIN orders AS o
        ON oi.order_id = o.order_id
    WHERE
        o.is_completed = TRUE
        OR o.order_id IS NULL
    GROUP BY
        p.product_id,
        p.product_name,
        p.category,
        p.price,
        p.price_tier

),

with_rankings AS (

    SELECT
        *,
        RANK() OVER (
            PARTITION BY category
            ORDER BY total_revenue DESC NULLS LAST
        ) AS category_revenue_rank,
        PERCENT_RANK() OVER (
            ORDER BY total_units_sold DESC NULLS LAST
        ) AS sales_percentile
    FROM product_sales

)

SELECT
    product_id,
    product_name,
    category,
    price,
    price_tier,
    COALESCE(order_count, 0) AS order_count,
    COALESCE(total_units_sold, 0) AS total_units_sold,
    COALESCE(total_revenue, 0) AS total_revenue,
    avg_order_value,
    first_order_date,
    last_order_date,
    category_revenue_rank,
    ROUND(sales_percentile, 4) AS sales_percentile,
    {% for tier in price_tiers %}
        CASE WHEN price_tier = '{{ tier }}' THEN 1 ELSE 0 END AS is_{{ tier }}_tier
        {%- if not loop.last %},{% endif %}
    {% endfor %}
FROM with_rankings
