{{ config(
    materialized='table',
    schema='gold',
    as_columnstore=false
) }}

SELECT
    s.company_name,
    s.cik,
    s.metric_name,
    s.concept,
    s.period_end,
    s.period_start,
    s.form,
    s.filed,
    s.value,
    s.unit,
    s.period_type,
    s.fiscal_year,
    s.fiscal_quarter
FROM {{ ref('silver_financials') }} s
