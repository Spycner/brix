{{
    config(
        materialized='incremental',
        unique_key='customer_id',
        incremental_strategy='merge',
        file_format='delta',
        post_hook=[
            "OPTIMIZE {{ this }} ZORDER BY (customer_id)"
        ],
        tags=['databricks', 'delta']
    )
}}

/*
    Example demonstrating Databricks MERGE INTO patterns with dbt incremental models.
    The merge strategy handles inserts, updates, and optionally deletes.
*/

WITH source_data AS (

    SELECT
        customer_id,
        full_name,
        email,
        status,
        is_active,
        customer_created_at,
        lifetime_value,
        customer_tier,
        CURRENT_TIMESTAMP() AS updated_at
    FROM {{ ref('dim_customers') }}

)

{% if is_incremental() %}

,existing_records AS (

    SELECT customer_id
    FROM {{ this }}

)

SELECT
    s.customer_id,
    s.full_name,
    s.email,
    s.status,
    s.is_active,
    s.customer_created_at,
    s.lifetime_value,
    s.customer_tier,
    s.updated_at,
    CASE
        WHEN e.customer_id IS NULL THEN 'insert'
        ELSE 'update'
    END AS _merge_action
FROM source_data AS s
LEFT JOIN existing_records AS e
    ON s.customer_id = e.customer_id

{% else %}

    SELECT
        customer_id,
        full_name,
        email,
        status,
        is_active,
        customer_created_at,
        lifetime_value,
        customer_tier,
        updated_at,
        'insert' AS _merge_action
    FROM source_data

{% endif %}
