/*
    Product Performance Analysis
    Demonstrates window functions and complex aggregations for SQLFluff testing.
*/

WITH product_metrics AS (

    SELECT
        p.product_id,
        p.product_name,
        p.category,
        p.price,
        p.price_tier,
        COUNT(DISTINCT oi.order_id) AS order_count,
        SUM(oi.quantity) AS units_sold,
        SUM(oi.line_total) AS total_revenue,
        AVG(oi.quantity) AS avg_units_per_order
    FROM {{ ref('stg_products') }} AS p
    LEFT JOIN {{ ref('stg_order_items') }} AS oi
        ON p.product_id = oi.product_id
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
        ROW_NUMBER() OVER (
            ORDER BY total_revenue DESC NULLS LAST
        ) AS overall_revenue_rank,
        ROW_NUMBER() OVER (
            PARTITION BY category
            ORDER BY total_revenue DESC NULLS LAST
        ) AS category_revenue_rank,
        PERCENT_RANK() OVER (
            ORDER BY units_sold DESC NULLS LAST
        ) AS sales_percentile,
        LAG(total_revenue) OVER (
            PARTITION BY category
            ORDER BY total_revenue DESC
        ) AS next_higher_revenue_in_category,
        SUM(total_revenue) OVER (
            PARTITION BY category
        ) AS category_total_revenue,
        SUM(total_revenue) OVER () AS grand_total_revenue
    FROM product_metrics

),

with_shares AS (

    SELECT
        *,
        ROUND(
            total_revenue * 100.0 / NULLIF(category_total_revenue, 0),
            2
        ) AS category_revenue_share,
        ROUND(
            total_revenue * 100.0 / NULLIF(grand_total_revenue, 0),
            2
        ) AS overall_revenue_share,
        CASE
            WHEN sales_percentile <= 0.2 THEN 'A - Top Performer'
            WHEN sales_percentile <= 0.5 THEN 'B - Good Performer'
            WHEN sales_percentile <= 0.8 THEN 'C - Average'
            ELSE 'D - Under Performer'
        END AS performance_grade
    FROM with_rankings

)

SELECT
    product_id,
    product_name,
    category,
    price,
    price_tier,
    COALESCE(order_count, 0) AS order_count,
    COALESCE(units_sold, 0) AS units_sold,
    COALESCE(total_revenue, 0) AS total_revenue,
    ROUND(avg_units_per_order, 2) AS avg_units_per_order,
    overall_revenue_rank,
    category_revenue_rank,
    ROUND(sales_percentile, 4) AS sales_percentile,
    category_revenue_share,
    overall_revenue_share,
    performance_grade
FROM with_shares
ORDER BY overall_revenue_rank
