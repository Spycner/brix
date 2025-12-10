{{
    config(
        materialized='view',
        tags=['staging', 'daily']
    )
}}

WITH source AS (

    SELECT * FROM {{ source('raw', 'orders') }}

),

transformed AS (

    SELECT
        order_id,
        customer_id,
        CAST(order_date AS DATE) AS order_date,
        CAST(total_amount AS DECIMAL(10, 2)) AS total_amount,
        status AS order_status,
        COALESCE(status = 'completed', FALSE) AS is_completed
    FROM source

)

SELECT * FROM transformed
