{{
    config(
        materialized='table',
        tags=['marts', 'dimension']
    )
}}

WITH products AS (

    SELECT * FROM {{ ref('stg_products') }}

),

product_sales AS (

    SELECT * FROM {{ ref('int_product_sales') }}

),

final AS (

    SELECT
        {{ dbt_utils.generate_surrogate_key(['p.product_id']) }} AS product_key,
        p.product_id,
        p.product_name,
        p.category,
        p.price,
        p.price_tier,
        p.created_at AS product_created_at,
        COALESCE(ps.order_count, 0) AS lifetime_order_count,
        COALESCE(ps.total_units_sold, 0) AS lifetime_units_sold,
        COALESCE(ps.total_revenue, 0) AS lifetime_revenue,
        ps.avg_order_value,
        ps.first_order_date,
        ps.last_order_date,
        ps.category_revenue_rank,
        CASE
            WHEN ps.total_units_sold >= 10 THEN 'high_performer'
            WHEN ps.total_units_sold >= 5 THEN 'moderate_performer'
            WHEN ps.total_units_sold > 0 THEN 'low_performer'
            ELSE 'no_sales'
        END AS performance_tier,
        CURRENT_TIMESTAMP() AS dbt_updated_at
    FROM products AS p
    LEFT JOIN product_sales AS ps
        ON p.product_id = ps.product_id

)

SELECT * FROM final
