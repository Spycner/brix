{{
    config(
        materialized='table',
        file_format='delta',
        tags=['databricks', 'ingestion']
    )
}}

/*
    Example demonstrating COPY INTO patterns for external data ingestion.
    In production, this would be executed via dbt run-operation or a pre-hook.

    COPY INTO syntax reference:
    COPY INTO target_table
    FROM (
        SELECT *
        FROM 'cloud_storage_path'
    )
    FILEFORMAT = PARQUET
    FORMAT_OPTIONS ('mergeSchema' = 'true')
    COPY_OPTIONS ('mergeSchema' = 'true')
*/

WITH simulated_external_load AS (

    /*
        Simulating data that would come from COPY INTO operation.
        In production, replace with actual external table or staging table.
    */
    SELECT
        event_id,
        event_type,
        event_timestamp,
        user_id,
        event_properties,
        ingestion_timestamp
    FROM (
        VALUES
        (1, 'page_view', TIMESTAMP '2024-01-15 10:30:00', 101, '{"page": "/home"}', CURRENT_TIMESTAMP()),
        (2, 'click', TIMESTAMP '2024-01-15 10:31:00', 101, '{"element": "buy_button"}', CURRENT_TIMESTAMP()),
        (3, 'purchase', TIMESTAMP '2024-01-15 10:32:00', 101, '{"amount": 99.99}', CURRENT_TIMESTAMP()),
        (4, 'page_view', TIMESTAMP '2024-01-15 11:00:00', 102, '{"page": "/products"}', CURRENT_TIMESTAMP()),
        (5, 'click', TIMESTAMP '2024-01-15 11:05:00', 102, '{"element": "add_cart"}', CURRENT_TIMESTAMP())
    )

),

parsed_events AS (

    SELECT
        event_id,
        event_type,
        event_timestamp,
        user_id,
        event_properties,
        ingestion_timestamp,
        DATE(event_timestamp) AS event_date,
        HOUR(event_timestamp) AS event_hour
    FROM simulated_external_load

)

SELECT * FROM parsed_events
