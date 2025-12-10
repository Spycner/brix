{{
    config(
        materialized='view',
        tags=['staging', 'daily']
    )
}}

WITH source AS (

    SELECT * FROM {{ source('raw', 'customers') }}

),

renamed AS (

    SELECT
        customer_id,
        first_name,
        last_name,
        CONCAT(first_name, ' ', last_name) AS full_name,
        LOWER(email) AS email,
        created_at,
        status,
        CASE
            WHEN status = 'active' THEN TRUE
            WHEN status = 'inactive' THEN FALSE
            WHEN status = 'churned' THEN FALSE
        END AS is_active
    FROM source

)

SELECT * FROM renamed
