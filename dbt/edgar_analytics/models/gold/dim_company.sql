{{ config(
    materialized='table',
    schema='gold',
    as_columnstore=false
) }}

SELECT
    ROW_NUMBER() OVER (ORDER BY company_name) AS company_key,
    company_name,
    MAX(cik) AS cik
FROM {{ ref('silver_financials') }}
GROUP BY company_name