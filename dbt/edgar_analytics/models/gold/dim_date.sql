{{ config(
    materialized='table',
    schema='gold',
    as_columnstore=false
) }}

SELECT
    ROW_NUMBER() OVER (ORDER BY period_end) AS date_key,
    period_end AS date_value,
    MAX(fiscal_year) AS fiscal_year,
    MAX(fiscal_quarter) AS fiscal_quarter,
    MAX(period_type) AS period_type
FROM {{ ref('silver_financials') }}
GROUP BY period_end