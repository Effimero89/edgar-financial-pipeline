{{ config(
    materialized='table',
    schema='gold',
    as_columnstore=false,
    post_hook="INSERT INTO dbo.pipeline_metadata (layer, last_refresh, row_count, records_added, status, duration_sec, source, triggered_by, error_message, environment) SELECT 'gold', GETUTCDATE(), COUNT(*), NULL, 'success', NULL, 'dbt', 'scheduled', NULL, 'dev' FROM dbo_gold.fact_financials"
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