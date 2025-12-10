{% macro optimize_table(relation, zorder_columns=none) %}
    {#
        Generate OPTIMIZE statement for Delta tables.
        Can be used in post-hooks or run-operations.

        Args:
            relation: The relation (table) to optimize
            zorder_columns: Optional list of columns for ZORDER

        Example:
            {{ optimize_table(this, ['customer_id', 'order_date']) }}
    #}

    {% set optimize_sql %}
        OPTIMIZE {{ relation }}
        {% if zorder_columns %}
        ZORDER BY ({{ zorder_columns | join(', ') }})
        {% endif %}
    {% endset %}

    {{ return(optimize_sql) }}

{% endmacro %}


{% macro vacuum_table(relation, retention_hours=168) %}
    {#
        Generate VACUUM statement for Delta tables.
        Default retention is 7 days (168 hours).

        Args:
            relation: The relation to vacuum
            retention_hours: Hours of history to retain (default: 168)

        Note: Requires delta.deletedFileRetentionDuration to allow < 7 days
    #}

    {% set vacuum_sql %}
        VACUUM {{ relation }} RETAIN {{ retention_hours }} HOURS
    {% endset %}

    {{ return(vacuum_sql) }}

{% endmacro %}


{% macro describe_history(relation, limit=10) %}
    {#
        Query Delta table history for auditing.

        Args:
            relation: The Delta table relation
            limit: Number of history entries to return
    #}

    SELECT
        version,
        timestamp,
        operation,
        operationParameters,
        operationMetrics
    FROM (DESCRIBE HISTORY {{ relation }})
    ORDER BY version DESC
    LIMIT {{ limit }}

{% endmacro %}


{% macro get_incremental_range(source_relation, date_column, lookback_days=3) %}
    {#
        Get date range for incremental loads with configurable lookback.

        Args:
            source_relation: Source table to check
            date_column: Date column to use for range
            lookback_days: Days to look back from max date

        Returns:
            CTE with start_date and end_date
    #}

    WITH date_range AS (

        SELECT
            DATE_SUB(MAX({{ date_column }}), {{ lookback_days }}) AS start_date,
            MAX({{ date_column }}) AS end_date
        FROM {{ source_relation }}

    )

{% endmacro %}


{% macro safe_divide(numerator, denominator, default=0) %}
    {#
        Safely divide two numbers, returning default on division by zero.

        Args:
            numerator: Dividend
            denominator: Divisor
            default: Value to return if denominator is 0 or NULL

        Returns:
            SQL CASE expression for safe division
    #}

    CASE
        WHEN {{ denominator }} IS NULL OR {{ denominator }} = 0
        THEN {{ default }}
        ELSE {{ numerator }} / {{ denominator }}
    END

{% endmacro %}


{% macro pivot_values(column_name, values_list, agg_function='SUM', value_column='1') %}
    {#
        Generate pivot column expressions.

        Args:
            column_name: Column to pivot on
            values_list: List of values to create columns for
            agg_function: Aggregation function (default: SUM)
            value_column: Column or expression to aggregate

        Example:
            {{ pivot_values('status', ['active', 'inactive', 'churned'], 'COUNT', '1') }}
    #}

    {% for value in values_list %}
    {{ agg_function }}(
        CASE WHEN {{ column_name }} = '{{ value }}' THEN {{ value_column }} ELSE 0 END
    ) AS {{ value | lower | replace(' ', '_') }}_count
    {%- if not loop.last %},{% endif %}
    {% endfor %}

{% endmacro %}
