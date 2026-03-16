# SEC EDGAR Financial Data Pipeline

> An end-to-end financial data engineering pipeline built on the Microsoft Azure stack, ingesting public company filings from the SEC EDGAR API and delivering analytics through Power BI.

**Author:** Tyler Mistretta  
**Stack:** Python · Azure Functions · ADLS Gen2 · Azure SQL · dbt Core · GitHub Actions · Power BI  
**Data Source:** [SEC EDGAR Financial Data API](https://data.sec.gov/api/xbrl/)

---

## Overview

This project demonstrates a production-grade data pipeline that extracts financial statement data for 63 public companies directly from the U.S. Securities and Exchange Commission's public EDGAR API. Raw filings are ingested into Azure Data Lake Storage Gen2, transformed through a Medallion architecture (Bronze → Silver → Gold) using dbt Core, and served via Azure SQL Database to a Power BI dashboard.

The pipeline runs fully automated on a daily schedule — Azure Functions handle ingestion and bronze loading, GitHub Actions orchestrates the dbt transformation run, and a pipeline metadata table provides end-to-end observability across all three layers. The architecture mirrors real-world enterprise data engineering patterns including idempotent data loading, environment-based resource naming, and version-controlled pipeline definitions.

---

## Architecture
```
SEC EDGAR API
      │
      ▼
Azure Function: edgar_ingest_batch1 (8:00am UTC)
Azure Function: edgar_ingest_batch2 (8:10am UTC)
Raw JSON → ADLS Gen2 /bronze (partitioned by date)
      │
      ▼
Azure Function: edgar_transform_batch1 (9:20am UTC)
Azure Function: edgar_transform_batch2 (9:30am UTC)
Flatten JSON → Azure SQL dbo.bronze_edgar_raw
      │
      ▼
GitHub Actions: dbt run (10:00am UTC daily)
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
| Function App | `func-edgar-ingest` | Hosts all four ingest and transform functions |

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
├── company_name
└── cik

dim_date
├── date_value
├── fiscal_year
├── fiscal_quarter
└── period_type
```

---

## Company Universe

The pipeline tracks 63 companies across technology, financials, healthcare, consumer, energy, and emerging growth sectors including:

**Large Cap / Index**
Apple, Microsoft, Amazon, Alphabet, Meta, Nvidia, Broadcom, Tesla, Eli Lilly, ExxonMobil, Chevron, JPMorgan, Johnson & Johnson, Walmart, Visa, Mastercard, Costco, Oracle, Netflix, AbbVie, P&G, Home Depot, Bank of America, GE Aerospace, Caterpillar, AMD, Cisco, Merck, Nike, Coca-Cola, McDonald's, RTX, Philip Morris, UnitedHealth, Applied Materials, Morgan Stanley, Lowe's, Goldman Sachs, BlackRock, Intuit, T-Mobile, ServiceNow, Salesforce, Qualcomm, Amgen, Honeywell, S&P Global, Charles Schwab, Booking Holdings, PepsiCo, Thermo Fisher, Danaher, Adobe, Texas Instruments, Palantir

**Small Cap / Emerging Growth**
Gambling.com, Enovix, AST SpaceMobile, Rocket Lab, Intuitive Machines, Planet Labs, Redwire, Red Cat Holdings

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
│       └── dbt_run.yml              # GitHub Actions workflow for daily dbt run
├── azure-functions/
│   ├── function_app.py              # All four ingest and transform functions
│   └── requirements.txt
├── dbt/
│   └── edgar_analytics/
│       ├── models/
│       │   ├── sources.yml          # Bronze source definition
│       │   ├── silver/
│       │   │   └── silver_financials.sql
│       │   └── gold/
│       │       ├── dim_company.sql
│       │       ├── dim_date.sql
│       │       └── fact_financials.sql
│       └── dbt_project.yml
├── powerbi/
│   ├── edgarFinancial.pbip          # Power BI project entry point
│   ├── edgarFinancial.Dataset/      # Data model, measures, and relationships (version controlled)
│   └── edgarFinancial.Report/       # Report layout and visuals (version controlled)
├── sql/
├── docs/                            # Architecture diagrams
├── infra/                           # Infrastructure-as-code (future)
├── notebooks/                       # Exploratory analysis (future)
└── adf/                             # Azure Data Factory (future)
```

---

## Medallion Architecture

| Layer | Storage | Format | Description |
|---|---|---|---|
| Bronze | ADLS Gen2 `/bronze` | JSON | Raw API responses, partitioned by ingestion date. Never modified. |
| Bronze SQL | Azure SQL `dbo.bronze_edgar_raw` | Table | Flattened rows from JSON — all companies, all metrics, ~32K rows per day. |
| Silver | Azure SQL `dbo_silver.silver_financials` | Table | Cleaned, deduplicated, normalized. One row per company/metric/period. |
| Gold | Azure SQL `dbo_gold.*` | Tables | Star schema optimized for Power BI. Fact and dimension tables. |

---

## Pipeline Observability

A `dbo.pipeline_metadata` table tracks every layer refresh with timestamp, row count, source system, and status. A view `dbo.vw_pipeline_latest_refresh` surfaces the most recent run per layer and is connected directly to the Power BI dashboard landing page, providing real-time visibility into pipeline health without leaving the report.

| Layer | Written By | Timing |
|---|---|---|
| Bronze | Azure Function post-transform | After each transform batch completes |
| Silver | dbt post-hook | After silver model run |
| Gold | dbt post-hook | After gold model run |

---

## Automation

The pipeline runs fully automated daily with no manual intervention required:

| Time (UTC) | Step | Tool |
|---|---|---|
| 8:00am | Pull raw JSON from SEC EDGAR → ADLS Gen2 (batch 1, 32 companies) | Azure Function |
| 8:10am | Pull raw JSON from SEC EDGAR → ADLS Gen2 (batch 2, 31 companies) | Azure Function |
| 9:20am | Flatten JSON → Azure SQL bronze table (batch 1) | Azure Function |
| 9:30am | Flatten JSON → Azure SQL bronze table (batch 2) | Azure Function |
| 10:00am | Run dbt Silver and Gold models | GitHub Actions |

---

## Key Engineering Decisions

**Batch splitting for Consumption plan timeout** — Azure Functions Consumption plan enforces a 10-minute maximum execution time. With 63 companies the ingest and transform operations exceed this limit as a single function. Splitting into two batches of 32 and 31 companies keeps each execution well within the timeout boundary without requiring a Premium plan.

**Azure Functions over ADF for JSON transformation** — The SEC EDGAR JSON structure is deeply nested and company-specific. Azure Functions with Python provide more flexibility for parsing complex JSON than ADF Data Flows, and fit naturally into the existing Function App infrastructure.

**pymssql over pyodbc** — Azure Functions run on Linux containers which lack the ODBC drivers required by pyodbc. pymssql provides a pure Python SQL Server connection that works without system-level driver installation.

**GitHub Actions for dbt orchestration** — dbt Core runs locally and in GitHub Actions, avoiding the need for dbt Cloud. The workflow installs the ODBC driver, configures the dbt profile from GitHub Secrets, and runs dbt on a cron schedule after the Azure Functions complete.

**Idempotent bronze loading** — The transform function deletes today's rows per company before inserting, ensuring the pipeline can be re-run safely without creating duplicates.

**GAAP Concept Normalization** — Different companies report equivalent metrics under different XBRL concept names. The pipeline maps multiple candidate concept names to a single normalized metric label (e.g., both `Revenues` and `RevenueFromContractWithCustomerExcludingAssessedTax` map to `revenue`).

**Deduplication Strategy** — The Silver model uses `ROW_NUMBER()` partitioned by company, concept, period end date, and form type, ordered by filed date descending. This retains the most recently filed version of each data point.

**Power BI Projects (.pbip) for version control** — The Power BI report is stored in the `.pbip` format rather than the binary `.pbix` format. This explodes the report into human-readable JSON and TMDL files, making DAX measures, relationships, and report layout fully diffable in Git.

**Pipeline metadata for observability** — A dedicated `dbo.pipeline_metadata` table records refresh timestamps, row counts, source system, and status for every layer on every run. This provides lightweight monitoring without external tooling and surfaces directly in the Power BI dashboard.

---

## Getting Started

### Prerequisites

- Azure subscription with contributor access
- Python 3.13
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
      driver: 'SQL Server'
      host: sql-edgar-analytics.database.windows.net
      port: 1433
      database: edgar-analytics
      schema: dbo
      user: 
      password: 
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
