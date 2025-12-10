{{
    config(
        materialized='view',
        tags=['staging', 'daily']
    )
}}

WITH source AS (

    SELECT * FROM {{ source('raw', 'products') }}

),

transformed AS (

    SELECT
        product_id,
        product_name,
        category,
        CAST(price AS DECIMAL(10, 2)) AS price,
        created_at,
        CASE
            WHEN price >= 1000 THEN 'premium'
            WHEN price >= 200 THEN 'standard'
            ELSE 'budget'
        END AS price_tier
    FROM source

)

SELECT * FROM transformed
