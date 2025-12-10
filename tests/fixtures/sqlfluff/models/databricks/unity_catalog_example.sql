{{
    config(
        materialized='view',
        tags=['databricks', 'unity_catalog']
    )
}}

/*
    Example demonstrating Unity Catalog 3-level namespace patterns.
    Unity Catalog uses: catalog.schema.table

    In production, configure via:
    - profiles.yml: catalog setting
    - dbt_project.yml: default schema
    - model config: database and schema overrides
*/

{% set catalog = var('unity_catalog', 'main') %}
{% set schema = var('unity_schema', 'analytics') %}

WITH catalog_reference_example AS (

    /*
        Direct 3-level namespace reference (for cross-catalog queries):
        SELECT * FROM catalog_name.schema_name.table_name

        With dbt, prefer using ref() and source() which handle namespaces automatically.
    */
    SELECT
        customer_key,
        customer_id,
        full_name,
        email,
        customer_tier,
        lifetime_value
    FROM {{ ref('dim_customers') }}

),

cross_schema_pattern AS (

    /*
        Example of how you might reference tables in different schemas.
        Use source() for external dependencies or ref() for dbt models.
    */
    SELECT
        c.customer_id,
        c.full_name,
        c.customer_tier,
        o.order_count
    FROM catalog_reference_example AS c
    LEFT JOIN (
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM {{ ref('fct_orders') }}
        GROUP BY customer_id
    ) AS o
        ON c.customer_id = o.customer_id

),

with_catalog_metadata AS (

    SELECT
        *,
        '{{ catalog }}' AS source_catalog,
        '{{ schema }}' AS source_schema,
        CURRENT_CATALOG() AS current_catalog,
        CURRENT_SCHEMA() AS current_schema
    FROM cross_schema_pattern

)

SELECT * FROM with_catalog_metadata
