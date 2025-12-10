{% macro generate_surrogate_key_custom(field_list) %}
    {#
        Custom surrogate key generation macro.
        Demonstrates macro definition patterns for SQLFluff testing.

        Args:
            field_list: List of column names to hash

        Returns:
            SQL expression that generates an MD5 hash of concatenated fields
    #}

    {% if field_list is string %}
        {% set field_list = [field_list] %}
    {% endif %}

    {% set formatted_fields = [] %}

    {% for field in field_list %}
        {% do formatted_fields.append(
            "COALESCE(CAST(" ~ field ~ " AS STRING), '_null_')"
        ) %}
    {% endfor %}

    MD5(CONCAT_WS('|', {{ formatted_fields | join(', ') }}))

{% endmacro %}


{% macro generate_hash_key(fields, separator='|') %}
    {#
        Alternative hash key generation with configurable separator.

        Args:
            fields: List of field names
            separator: Character to separate concatenated values (default: '|')

        Returns:
            SHA256 hash expression
    #}

    {% set field_expressions = [] %}

    {% for field in fields %}
        {% do field_expressions.append(
            "COALESCE(CAST(" ~ field ~ " AS STRING), '')"
        ) %}
    {% endfor %}

    SHA2(CONCAT_WS('{{ separator }}', {{ field_expressions | join(', ') }}), 256)

{% endmacro %}
