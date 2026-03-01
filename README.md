# SEC EDGAR Financial Data Pipeline

> An end-to-end financial data engineering pipeline built on the Microsoft Azure stack, ingesting public company filings from the SEC EDGAR API and delivering executive-level analytics through Power BI.

**Author:** Tyler Mistretta  
**Stack:** Python · Azure Data Factory · ADLS Gen2 · Azure SQL · dbt · Power BI  
**Data Source:** [SEC EDGAR Financial Data API](https://data.sec.gov/api/xbrl/)

---

## Overview

This project demonstrates a production-grade data pipeline that extracts financial statement data for Dow 30 companies directly from the U.S. Securities and Exchange Commission's public EDGAR API. Raw filings are ingested into Azure Data Lake Storage Gen2, transformed through a Medallion architecture (Bronze → Silver → Gold), and served via Azure SQL Database to a Power BI semantic model with time-intelligence reporting.

The pipeline runs on a daily schedule orchestrated by Azure Data Factory and is designed to mirror real-world enterprise data engineering patterns including secret management via Azure Key Vault, environment-based resource naming conventions, and version-controlled pipeline definitions.

---

## Architecture

```
SEC EDGAR API
      │
      ▼
Azure Data Factory (HTTP Connector + Scheduled Trigger)
      │
      ▼
ADLS Gen2 ── /bronze  (raw JSON, partitioned by date)
          ── /silver  (cleaned, conformed Parquet)
          ── /gold    (aggregated, query-ready)
      │
      ▼
Azure SQL Database (Star Schema Serving Layer)
      │
      ▼
Power BI Service (Semantic Model + Executive Dashboard)
```

### Azure Resources

| Resource | Name | Purpose |
|---|---|---|
| Resource Group | `rg-edgar-analytics-dev` | Logical container for all resources |
| Storage Account (ADLS Gen2) | `stedgaranalytics` | Data lake — Bronze / Silver / Gold layers |
| Azure SQL Database | `edgar-analytics` | Serving layer — star schema for Power BI |
| Azure Data Factory | `adf-edgar-analytics` | Orchestration and pipeline scheduling |
| Azure Key Vault | `kv-edgar-analytics` | Secrets and connection string management |

---

## Data Model

The Gold layer is modeled as a star schema optimized for time-series financial analysis.

```
fact_financials
├── fact_key          (surrogate key)
├── company_key       (FK → dim_company)
├── date_key          (FK → dim_date)
├── metric            (Revenue, NetIncome, EPS, OperatingCashFlow, TotalAssets, TotalDebt)
├── period_type       (Annual / Quarterly)
├── fiscal_year
├── fiscal_period
└── value

dim_company
├── company_key
├── company
├── cik
└── sector

dim_date
├── date_key
├── date
├── year
├── quarter
├── month
├── month_name
└── quarter_label
```

---

## Company Universe

The pipeline tracks the following 10 companies across 5 GICS sectors:

| Company | Sector |
|---|---|
| Apple Inc. | Technology |
| Microsoft Corporation | Technology |
| Amazon | Consumer Discretionary |
| Nike | Consumer Discretionary |
| McDonald's | Consumer Discretionary |
| Walmart | Consumer Staples |
| Coca-Cola | Consumer Staples |
| JPMorgan Chase | Financials |
| Visa | Financials |
| Johnson & Johnson | Healthcare |

---

## Metrics Tracked

| Metric | GAAP Concept |
|---|---|
| Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` / `Revenues` |
| Net Income | `NetIncomeLoss` |
| Operating Cash Flow | `NetCashProvidedByUsedInOperatingActivities` |
| Total Assets | `Assets` |
| Total Debt | `LongTermDebt` |
| EPS | `EarningsPerShareBasic` / `EarningsPerShareDiluted` |

---

## Repository Structure

```
edgar-financial-pipeline/
├── README.md
├── infra/                  # Azure Bicep / ARM templates for resource provisioning
├── adf/                    # Exported Azure Data Factory pipeline definitions (JSON)
├── notebooks/              # Jupyter notebooks for exploration and development
├── dbt/
│   ├── models/
│   │   ├── bronze/         # Raw landing models
│   │   ├── silver/         # Cleaned and conformed models
│   │   └── gold/           # Star schema — fact and dimension tables
│   └── tests/              # dbt data quality tests
├── sql/                    # DDL scripts for Azure SQL schema
├── powerbi/                # Power BI .pbix file
└── docs/                   # Architecture diagrams and data dictionary
```

---

## Medallion Architecture

| Layer | Storage | Format | Description |
|---|---|---|---|
| Bronze | ADLS Gen2 `/bronze` | JSON | Raw API responses, partitioned by ingestion date. Never modified. |
| Silver | ADLS Gen2 `/silver` | Parquet | Cleaned, typed, deduplicated. Annual and quarterly records separated. |
| Gold | Azure SQL Database | Tables | Star schema optimized for Power BI. Fact and dimension tables with surrogate keys. |

---

## Power BI Reporting

The Power BI report connects to the Azure SQL Gold layer and includes:

- **Executive Summary** — Revenue, Net Income, and EPS trends across all companies
- **Company Deep Dive** — Drill-through page for per-company financial history
- **Comparative Analysis** — Sector-level benchmarking and peer comparison
- **Time Intelligence** — Year-over-year growth, rolling 12-month averages, and period-over-period variance using DAX

---

## Key Engineering Decisions

**GAAP Concept Normalization** — Different companies report equivalent metrics under different XBRL concept names. The pipeline implements a candidate fallback system that attempts multiple concept names per metric in priority order, ensuring consistent coverage across filers.

**Deduplication Strategy** — The same financial figure can appear across multiple filings (e.g., a quarterly figure restated in the subsequent annual filing). The Silver layer deduplicates by retaining the most recently filed version per company, metric, end date, and form type.

**Secret Management** — All connection strings and API credentials are stored in Azure Key Vault and referenced by ADF linked services via managed identity. No credentials are hardcoded in pipeline definitions or committed to source control.

**Environment Naming Convention** — All Azure resources follow the `{type}-{workload}-{environment}` naming pattern (e.g., `adf-edgar-analytics-dev`) consistent with Microsoft's Cloud Adoption Framework.

---

## Getting Started

### Prerequisites

- Azure subscription with contributor access
- Python 3.9+
- dbt Core (`pip install dbt-sqlserver`)
- Power BI Desktop

### Clone the Repository

```bash
git clone https://github.com/Effimero89/edgar-financial-pipeline.git
cd edgar-financial-pipeline
```

### Install Python Dependencies

```bash
pip install requests pandas pyodbc sqlalchemy
```

### Configure dbt

Update `dbt/profiles.yml` with your Azure SQL connection details. Reference connection strings from Key Vault — do not hardcode credentials.

### Run the Pipeline

```bash
# Run dbt transformations
cd dbt
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

MIT License — see `LICENSE` for details.

---

*Built by Tyler Mistretta as a portfolio demonstration of enterprise data engineering on the Microsoft Azure stack.*
