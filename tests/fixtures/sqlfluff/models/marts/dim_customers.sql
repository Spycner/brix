{{
    config(
        materialized='table',
        tags=['marts', 'dimension']
    )
}}

WITH customers AS (

    SELECT * FROM {{ ref('stg_customers') }}

),

customer_orders AS (

    SELECT
        customer_id,
        COUNT(DISTINCT order_id) AS lifetime_order_count,
        SUM(total_amount) AS lifetime_value,
        MIN(order_date) AS first_order_date,
        MAX(order_date) AS most_recent_order_date,
        AVG(total_amount) AS avg_order_value
    FROM {{ ref('int_customer_orders') }}
    GROUP BY customer_id

),

final AS (

    SELECT
        {{ dbt_utils.generate_surrogate_key(['c.customer_id']) }} AS customer_key,
        c.customer_id,
        c.first_name,
        c.last_name,
        c.full_name,
        c.email,
        c.status,
        c.is_active,
        c.created_at AS customer_created_at,
        COALESCE(co.lifetime_order_count, 0) AS lifetime_order_count,
        COALESCE(co.lifetime_value, 0) AS lifetime_value,
        co.first_order_date,
        co.most_recent_order_date,
        co.avg_order_value,
        CASE
            WHEN co.lifetime_value >= 2000 THEN 'platinum'
            WHEN co.lifetime_value >= 1000 THEN 'gold'
            WHEN co.lifetime_value >= 500 THEN 'silver'
            WHEN co.lifetime_value > 0 THEN 'bronze'
            ELSE 'prospect'
        END AS customer_tier,
        DATEDIFF(DAY, co.most_recent_order_date, CURRENT_DATE()) AS days_since_last_order,
        CURRENT_TIMESTAMP() AS dbt_updated_at
    FROM customers AS c
    LEFT JOIN customer_orders AS co
        ON c.customer_id = co.customer_id

)

SELECT * FROM final
