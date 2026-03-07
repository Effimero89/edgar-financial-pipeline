{{ config(
    materialized='table',
    schema='gold',
    as_columnstore=false
) }}

SELECT DISTINCT
    ROW_NUMBER() OVER (ORDER BY company_name) AS company_key,
    company_name,
    cik
FROM {{ ref('silver_financials') }}