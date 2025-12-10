{% test positive_values(model, column_name) %}
    {#
        Generic test to ensure all values in a column are positive.
        Demonstrates custom generic test patterns for SQLFluff.

        Args:
            model: The model to test
            column_name: The column that should contain positive values

        Usage in schema.yml:
            columns:
              - name: price
                data_tests:
                  - positive_values
    #}

    SELECT
        {{ column_name }} AS failing_value,
        COUNT(*) AS failure_count
    FROM {{ model }}
    WHERE {{ column_name }} IS NOT NULL
        AND {{ column_name }} <= 0
    GROUP BY {{ column_name }}

{% endtest %}


{% test within_range(model, column_name, min_value, max_value) %}
    {#
        Generic test to ensure values fall within a specified range.

        Args:
            model: The model to test
            column_name: The column to validate
            min_value: Minimum acceptable value (inclusive)
            max_value: Maximum acceptable value (inclusive)

        Usage in schema.yml:
            columns:
              - name: quantity
                data_tests:
                  - within_range:
                      min_value: 1
                      max_value: 1000
    #}

    SELECT
        {{ column_name }} AS failing_value,
        CASE
            WHEN {{ column_name }} < {{ min_value }} THEN 'below_minimum'
            WHEN {{ column_name }} > {{ max_value }} THEN 'above_maximum'
        END AS failure_reason
    FROM {{ model }}
    WHERE {{ column_name }} IS NOT NULL
        AND ({{ column_name }} < {{ min_value }} OR {{ column_name }} > {{ max_value }})

{% endtest %}
