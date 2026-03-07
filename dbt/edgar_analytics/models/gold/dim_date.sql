{{ config(
    materialized='table',
    schema='gold',
    as_columnstore=false
) }}

SELECT DISTINCT
    ROW_NUMBER() OVER (ORDER BY period_end) AS date_key,
    period_end AS date_value,
    fiscal_year,
    fiscal_quarter,
    period_type
FROM {{ ref('silver_financials') }}