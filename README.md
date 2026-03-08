# SEC EDGAR Financial Data Pipeline

> An end-to-end financial data engineering pipeline built on the Microsoft Azure stack, ingesting public company filings from the SEC EDGAR API and delivering analytics through Power BI.

**Author:** Tyler Mistretta  
**Stack:** Python · Azure Functions · ADLS Gen2 · Azure SQL · dbt Core · GitHub Actions · Power BI  
**Data Source:** [SEC EDGAR Financial Data API](https://data.sec.gov/api/xbrl/)

---

## Overview

This project demonstrates a production-grade data pipeline that extracts financial statement data for 10 major companies directly from the U.S. Securities and Exchange Commission's public EDGAR API. Raw filings are ingested into Azure Data Lake Storage Gen2, transformed through a Medallion architecture (Bronze → Silver → Gold) using dbt Core, and served via Azure SQL Database to a Power BI dashboard.

The pipeline runs fully automated on a daily schedule — Azure Functions handle ingestion and bronze loading, and GitHub Actions orchestrates the dbt transformation run. The architecture mirrors real-world enterprise data engineering patterns including idempotent data loading, environment-based resource naming, and version-controlled pipeline definitions.

---

## Architecture

```
SEC EDGAR API
      │
      ▼
Azure Function: edgar_ingest (8:00am UTC daily)
Raw JSON → ADLS Gen2 /bronze (partitioned by date)
      │
      ▼
Azure Function: edgar_transform (8:30am UTC daily)
Flatten JSON → Azure SQL dbo.bronze_edgar_raw
      │
      ▼
GitHub Actions: dbt run (9:00am UTC daily)
      │
      ├── dbo_silver.silver_financials
      │       (cleaned, deduplicated, normalized)
      │
      └── dbo_gold.fact_financials
          dbo_gold.dim_company
          dbo_gold.dim_date
      │
      ▼
Power BI Dashboard
```

### Azure Resources

| Resource | Name | Purpose |
|---|---|---|
| Resource Group | `rg-edgar-analytics-dev` | Logical container for all resources |
| Storage Account (ADLS Gen2) | `stedgaranalytics` | Data lake — Bronze JSON landing zone |
| Azure SQL Database | `edgar-analytics` | Serving layer — Bronze, Silver, and Gold tables |
| Azure Data Factory | `adf-edgar-analytics` | Available for future orchestration expansion |
| Azure Key Vault | `kv-edgar-analytics` | Secrets and connection string management |
| Function App | `func-edgar-ingest` | Hosts edgar_ingest and edgar_transform functions |

---

## Data Model

The Gold layer is modeled as a star schema optimized for time-series financial analysis.

```
fact_financials
├── company_name
├── cik
├── metric_name       (revenue, net_income, eps_basic, eps_diluted, total_assets, operating_income, stockholders_equity)
├── concept           (raw GAAP concept name)
├── period_end
├── period_start
├── form              (10-K / 10-Q)
├── filed
├── value
├── unit
├── period_type       (annual / quarterly)
├── fiscal_year
└── fiscal_quarter

dim_company
├── company_key
├── company_name
└── cik

dim_date
├── date_key
├── date_value
├── fiscal_year
├── fiscal_quarter
└── period_type
```

---

## Company Universe

The pipeline tracks the following 10 companies:

| Company | Ticker | Sector |
|---|---|---|
| Apple Inc. | AAPL | Technology |
| Microsoft Corporation | MSFT | Technology |
| Amazon | AMZN | Consumer Discretionary |
| Nike | NKE | Consumer Discretionary |
| McDonald's | MCD | Consumer Discretionary |
| Walmart | WMT | Consumer Staples |
| Coca-Cola | KO | Consumer Staples |
| JPMorgan Chase | JPM | Financials |
| Visa | V | Financials |
| Johnson & Johnson | JNJ | Healthcare |

---

## Metrics Tracked

| Metric | GAAP Concepts |
|---|---|
| Revenue | `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax` |
| Net Income | `NetIncomeLoss` |
| EPS Basic | `EarningsPerShareBasic` |
| EPS Diluted | `EarningsPerShareDiluted` |
| Total Assets | `Assets` |
| Operating Income | `OperatingIncomeLoss` |
| Stockholders Equity | `StockholdersEquity` |

---

## Repository Structure

```
edgar-financial-pipeline/
├── README.md
├── .github/
│   └── workflows/
│       └── dbt_run.yml         # GitHub Actions workflow for daily dbt run
├── azure-functions/
│   ├── function_app.py         # edgar_ingest + edgar_transform functions
│   └── requirements.txt
├── dbt/
│   └── edgar_analytics/
│       ├── models/
│       │   ├── silver/
│       │   │   ├── silver_financials.sql
│       │   │   └── sources.yml
│       │   └── gold/
│       │       ├── dim_company.sql
│       │       ├── dim_date.sql
│       │       └── fact_financials.sql
│       └── dbt_project.yml
├── powerbi/
│   └── edgarFinancial.pbix
└── docs/                       # Architecture diagrams
```

---

## Medallion Architecture

| Layer | Storage | Format | Description |
|---|---|---|---|
| Bronze | ADLS Gen2 `/bronze` | JSON | Raw API responses, partitioned by ingestion date. Never modified. |
| Bronze SQL | Azure SQL `dbo.bronze_edgar_raw` | Table | Flattened rows from JSON — all companies, all metrics, ~15K rows per day. |
| Silver | Azure SQL `dbo_silver.silver_financials` | Table | Cleaned, deduplicated, normalized. One row per company/metric/period. |
| Gold | Azure SQL `dbo_gold.*` | Tables | Star schema optimized for Power BI. Fact and dimension tables. |

---

## Automation

The pipeline runs fully automated daily with no manual intervention required:

| Time (UTC) | Step | Tool |
|---|---|---|
| 8:00am | Pull raw JSON from SEC EDGAR → ADLS Gen2 bronze | Azure Function |
| 8:30am | Flatten JSON → Azure SQL bronze table | Azure Function |
| 9:00am | Run dbt Silver and Gold models | GitHub Actions |

---

## Key Engineering Decisions

**Azure Functions over ADF for JSON transformation** — The SEC EDGAR JSON structure is deeply nested and company-specific. Azure Functions with Python provide more flexibility for parsing complex JSON than ADF Data Flows, and fit naturally into the existing Function App infrastructure.

**pymssql over pyodbc** — Azure Functions run on Linux containers which lack the ODBC drivers required by pyodbc. pymssql provides a pure Python SQL Server connection that works without system-level driver installation.

**GitHub Actions for dbt orchestration** — dbt Core runs locally and in GitHub Actions, avoiding the need for dbt Cloud. The workflow installs the ODBC driver, configures the dbt profile from GitHub Secrets, and runs dbt on a cron schedule after the Azure Functions complete.

**Idempotent bronze loading** — The transform function deletes today's rows before inserting, ensuring the pipeline can be re-run safely without creating duplicates.

**GAAP Concept Normalization** — Different companies report equivalent metrics under different XBRL concept names. The pipeline maps multiple candidate concept names to a single normalized metric label (e.g., both `Revenues` and `RevenueFromContractWithCustomerExcludingAssessedTax` map to `revenue`).

**Deduplication Strategy** — The Silver model uses `ROW_NUMBER()` partitioned by company, concept, period end date, and form type, ordered by filed date descending. This retains the most recently filed version of each data point.

---

## Getting Started

### Prerequisites

- Azure subscription with contributor access
- Python 3.11
- dbt Core (`pip install dbt-sqlserver==1.9.0`)
- Power BI Desktop

### Clone the Repository

```bash
git clone https://github.com/Effimero89/edgar-financial-pipeline.git
cd edgar-financial-pipeline
```

### Configure dbt

Create `~/.dbt/profiles.yml` with your Azure SQL connection details:

```yaml
edgar_analytics:
  outputs:
    dev:
      type: sqlserver
      driver: 'ODBC Driver 18 for SQL Server'
      host: sql-edgar-analytics.database.windows.net
      port: 1433
      database: edgar-analytics
      schema: dbo
      user: <your_admin_user>
      password: <your_password>
      threads: 4
  target: dev
```

### Run dbt Transformations

```bash
cd dbt/edgar_analytics
dbt run
dbt test
```

---

## SEC EDGAR API

This project uses the SEC's free public EDGAR Financial Data API. No API key is required. A `User-Agent` header identifying the requesting application is required per SEC guidelines.

- Base URL: `https://data.sec.gov/api/xbrl/companyfacts/`
- Rate limit: Requests are throttled to 0.5 seconds between calls to respect SEC guidelines
- Documentation: [https://www.sec.gov/edgar/sec-api-documentation](https://www.sec.gov/edgar/sec-api-documentation)

---

## License

MIT License

---

*Built by Tyler Mistretta as a portfolio demonstration of enterprise data engineering on the Microsoft Azure stack.*
