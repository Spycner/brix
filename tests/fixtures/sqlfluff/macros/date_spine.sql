{% macro date_spine(start_date, end_date, datepart='day') %}
    {#
        Generate a date spine between two dates.
        Demonstrates loops, conditionals, and complex Jinja patterns.

        Args:
            start_date: Start date expression (string or date literal)
            end_date: End date expression (string or date literal)
            datepart: Granularity ('day', 'week', 'month', 'quarter', 'year')

        Returns:
            CTE that generates date series
    #}

    {% set datepart_map = {
        'day': 'DAY',
        'week': 'WEEK',
        'month': 'MONTH',
        'quarter': 'QUARTER',
        'year': 'YEAR'
    } %}

    {% set sql_datepart = datepart_map.get(datepart | lower, 'DAY') %}

    WITH date_spine AS (

        SELECT
            EXPLODE(
                SEQUENCE(
                    DATE({{ start_date }}),
                    DATE({{ end_date }}),
                    INTERVAL 1 {{ sql_datepart }}
                )
            ) AS date_{{ datepart }}

    )

    SELECT
        date_{{ datepart }},
        YEAR(date_{{ datepart }}) AS year_num,
        {% if datepart in ['day', 'week'] %}
        MONTH(date_{{ datepart }}) AS month_num,
        DAY(date_{{ datepart }}) AS day_num,
        DAYOFWEEK(date_{{ datepart }}) AS day_of_week,
        {% endif %}
        {% if datepart == 'day' %}
        CASE
            WHEN DAYOFWEEK(date_{{ datepart }}) IN (1, 7) THEN FALSE
            ELSE TRUE
        END AS is_weekday,
        {% endif %}
        DATE_FORMAT(date_{{ datepart }}, 'yyyyMM') AS year_month_key
    FROM date_spine

{% endmacro %}


{% macro fiscal_date_spine(start_date, end_date, fiscal_year_start_month=4) %}
    {#
        Generate date spine with fiscal year calculations.

        Args:
            start_date: Start date
            end_date: End date
            fiscal_year_start_month: Month fiscal year begins (default: April = 4)
    #}

    WITH calendar_dates AS (

        {{ date_spine(start_date, end_date, 'day') }}

    ),

    with_fiscal AS (

        SELECT
            date_day,
            year_num AS calendar_year,
            month_num AS calendar_month,
            CASE
                WHEN month_num >= {{ fiscal_year_start_month }}
                THEN year_num
                ELSE year_num - 1
            END AS fiscal_year,
            CASE
                WHEN month_num >= {{ fiscal_year_start_month }}
                THEN month_num - {{ fiscal_year_start_month }} + 1
                ELSE month_num + (12 - {{ fiscal_year_start_month }}) + 1
            END AS fiscal_month,
            CEIL(
                CASE
                    WHEN month_num >= {{ fiscal_year_start_month }}
                    THEN month_num - {{ fiscal_year_start_month }} + 1
                    ELSE month_num + (12 - {{ fiscal_year_start_month }}) + 1
                END / 3.0
            ) AS fiscal_quarter
        FROM calendar_dates

    )

    SELECT * FROM with_fiscal

{% endmacro %}
