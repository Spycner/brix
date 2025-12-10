{{
    config(
        materialized='view',
        tags=['staging', 'daily']
    )
}}

WITH source AS (

    SELECT * FROM {{ source('raw', 'order_items') }}

),

transformed AS (

    SELECT
        order_item_id,
        order_id,
        product_id,
        quantity,
        CAST(unit_price AS DECIMAL(10, 2)) AS unit_price,
        CAST(quantity * unit_price AS DECIMAL(10, 2)) AS line_total
    FROM source

)

SELECT * FROM transformed
