{{ config(
    materialized='table',
    schema='silver',
    as_columnstore=false
) }}

WITH deduped AS (
    SELECT
        company_name,
        cik,
        metric_name,
        concept,
        period_end,
        period_start,
        form,
        filed,
        value,
        unit,
        ingestion_date,
        ROW_NUMBER() OVER (
            PARTITION BY company_name, concept, period_end, form
            ORDER BY filed DESC, ingestion_date DESC
        ) AS rn
    FROM {{ source('bronze', 'bronze_edgar_raw') }}
    WHERE value IS NOT NULL
        AND period_end IS NOT NULL
        AND value != 0
)

SELECT
    company_name,
    cik,
    metric_name,
    concept,
    period_end,
    period_start,
    form,
    filed,
    value,
    unit,
    ingestion_date,
    CASE
        WHEN form = '10-K' THEN 'annual'
        WHEN form = '10-Q' THEN 'quarterly'
    END AS period_type,
    YEAR(period_end) AS fiscal_year,
    DATEPART(QUARTER, period_end) AS fiscal_quarter
FROM deduped
WHERE rn = 1