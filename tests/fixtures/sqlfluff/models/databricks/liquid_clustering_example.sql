{{
    config(
        materialized='table',
        file_format='delta',
        liquid_clustered_by=['order_date', 'customer_id'],
        tblproperties={
            'delta.enableChangeDataFeed': 'true',
            'delta.autoOptimize.optimizeWrite': 'true',
            'delta.autoOptimize.autoCompact': 'true'
        },
        tags=['databricks', 'liquid_clustering']
    )
}}

/*
    Example demonstrating Databricks Liquid Clustering (replacement for ZORDER).
    Liquid Clustering provides:
    - Automatic data layout optimization
    - No manual OPTIMIZE needed
    - Better performance for evolving query patterns

    Table properties for Delta Lake optimization:
    - delta.enableChangeDataFeed: Enable CDF for downstream CDC
    - delta.autoOptimize.optimizeWrite: Coalesce small files on write
    - delta.autoOptimize.autoCompact: Automatic compaction
*/

WITH orders AS (

    SELECT * FROM {{ ref('fct_orders') }}

),

order_items AS (

    SELECT * FROM {{ ref('stg_order_items') }}

),

products AS (

    SELECT * FROM {{ ref('stg_products') }}

),

detailed_orders AS (

    SELECT
        o.order_key,
        o.order_id,
        o.customer_key,
        o.customer_id,
        o.order_date,
        o.order_month,
        o.order_year,
        o.total_amount,
        o.order_status,
        oi.order_item_id,
        oi.product_id,
        p.product_name,
        p.category,
        oi.quantity,
        oi.unit_price,
        oi.line_total
    FROM orders AS o
    INNER JOIN order_items AS oi
        ON o.order_id = oi.order_id
    INNER JOIN products AS p
        ON oi.product_id = p.product_id

),

with_partitioning_hint AS (

    /*
        Data is clustered by order_date and customer_id for optimal
        performance on time-series and customer-centric queries.
    */
    SELECT
        *,
        DATE_FORMAT(order_date, 'yyyyMM') AS partition_month,
        HASH(customer_id) % 100 AS customer_bucket
    FROM detailed_orders

)

SELECT * FROM with_partitioning_hint
