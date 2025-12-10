/*
    Customer Cohort Analysis
    Demonstrates complex analytical query patterns for SQLFluff testing.

    This analysis calculates:
    - Monthly cohorts based on first purchase
    - Retention rates by cohort
    - Revenue by cohort over time
*/

WITH customer_first_order AS (

    SELECT
        customer_id,
        MIN(order_date) AS first_order_date,
        DATE_TRUNC('MONTH', MIN(order_date)) AS cohort_month
    FROM {{ ref('fct_orders') }}
    GROUP BY customer_id

),

orders_with_cohort AS (

    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        o.total_amount,
        c.cohort_month,
        DATE_TRUNC('MONTH', o.order_date) AS order_month,
        MONTHS_BETWEEN(
            DATE_TRUNC('MONTH', o.order_date),
            c.cohort_month
        ) AS months_since_first_order
    FROM {{ ref('fct_orders') }} AS o
    INNER JOIN customer_first_order AS c
        ON o.customer_id = c.customer_id

),

cohort_size AS (

    SELECT
        cohort_month,
        COUNT(DISTINCT customer_id) AS cohort_customers
    FROM customer_first_order
    GROUP BY cohort_month

),

cohort_activity AS (

    SELECT
        cohort_month,
        months_since_first_order,
        COUNT(DISTINCT customer_id) AS active_customers,
        COUNT(DISTINCT order_id) AS order_count,
        SUM(total_amount) AS total_revenue,
        AVG(total_amount) AS avg_order_value
    FROM orders_with_cohort
    GROUP BY
        cohort_month,
        months_since_first_order

),

cohort_retention AS (

    SELECT
        ca.cohort_month,
        ca.months_since_first_order,
        cs.cohort_customers,
        ca.active_customers,
        ca.order_count,
        ca.total_revenue,
        ca.avg_order_value,
        ROUND(
            ca.active_customers * 100.0 / cs.cohort_customers,
            2
        ) AS retention_rate,
        SUM(ca.total_revenue) OVER (
            PARTITION BY ca.cohort_month
            ORDER BY ca.months_since_first_order
        ) AS cumulative_revenue
    FROM cohort_activity AS ca
    INNER JOIN cohort_size AS cs
        ON ca.cohort_month = cs.cohort_month

)

SELECT
    cohort_month,
    months_since_first_order,
    cohort_customers,
    active_customers,
    order_count,
    total_revenue,
    avg_order_value,
    retention_rate,
    cumulative_revenue,
    ROUND(
        cumulative_revenue / cohort_customers,
        2
    ) AS ltv_per_customer
FROM cohort_retention
ORDER BY
    cohort_month,
    months_since_first_order
