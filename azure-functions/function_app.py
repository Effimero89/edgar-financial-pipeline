import azure.functions as func
import logging
import json
import requests
import time
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import os
import pymssql

app = func.FunctionApp()

# Company universe - CIK numbers
COMPANIES = {
    "Apple":              "0000320193",
    "Microsoft":          "0000789019",
    "Amazon":             "0001018724",
    "JPMorgan":           "0000019617",
    "Johnson_Johnson":    "0000200406",
    "Walmart":            "0000104169",
    "Nike":               "0000320187",
    "Coca_Cola":          "0000021344",
    "McDonalds":          "0000063908",
    "Visa":               "0001403161"
}

HEADERS = {
    "User-Agent": "Tyler Mistretta effimero89@gmail.com"
}

BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts/"

@app.timer_trigger(
    schedule="0 0 8 * * *",  # Daily at 8am UTC
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=False
)
def edgar_ingest(myTimer: func.TimerRequest) -> None:
    logging.info(f"SEC EDGAR ingestion started at {datetime.utcnow()}")

    # Get connection string from environment variable (set in Azure, pulled from Key Vault)
    connection_string = os.environ["ADLS_CONNECTION_STRING"]
    blob_service = BlobServiceClient.from_connection_string(connection_string)
    container = blob_service.get_container_client("bronze")

    ingestion_date = datetime.utcnow().strftime("%Y/%m/%d")
    success_count = 0
    error_count = 0

    for company_name, cik in COMPANIES.items():
        try:
            logging.info(f"Pulling {company_name}...")
            url = f"{BASE_URL}CIK{cik}.json"
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()

            raw_json = response.json()

            # Build blob path: bronze/YYYY/MM/DD/company.json
            blob_path = f"{ingestion_date}/{company_name}.json"

            blob_client = container.get_blob_client(blob_path)
            blob_client.upload_blob(
                json.dumps(raw_json),
                overwrite=True,
                content_settings=None
            )

            logging.info(f"  Saved to bronze/{blob_path}")
            success_count += 1
            time.sleep(0.5)

        except Exception as e:
            logging.error(f"  ERROR on {company_name}: {str(e)}")
            error_count += 1

@app.timer_trigger(
    schedule="0 30 8 * * *",  # Daily at 8:30am UTC (30 min after ingest)
    arg_name="transformTimer",
    run_on_startup=False,
    use_monitor=False
)
def edgar_transform(transformTimer: func.TimerRequest) -> None:
    logging.info(f"SEC EDGAR transform started at {datetime.utcnow()}")

    try:
        test_pw = os.environ.get("SQL_PASSWORD", "NOT FOUND")
        logging.info(f"SQL_PASSWORD length: {len(test_pw)}, starts with: {test_pw[:3]}")
    except Exception as e:
        logging.error(f"Debug error: {str(e)}")
        
    connection_string = os.environ["ADLS_CONNECTION_STRING"]

    blob_service = BlobServiceClient.from_connection_string(connection_string)
    container = blob_service.get_container_client("bronze")

    ingestion_date = datetime.utcnow().strftime("%Y/%m/%d")

    METRICS = {
        "Revenues": "revenue",
        "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
        "NetIncomeLoss": "net_income",
        "EarningsPerShareBasic": "eps_basic",
        "EarningsPerShareDiluted": "eps_diluted",
        "Assets": "total_assets",
        "StockholdersEquity": "stockholders_equity",
        "OperatingIncomeLoss": "operating_income"
    }

    try:
        conn = pymssql.connect(
            server='sql-edgar-analytics.database.windows.net',
            user='edgaradmin',
            password=os.environ["SQL_PASSWORD"],
            database='edgar-analytics'
        )
        logging.info("SQL connection successful")
    except Exception as e:
        logging.error(f"SQL connection failed: {str(e)}")
        raise

    cursor = conn.cursor()

    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'bronze_edgar_raw')
        CREATE TABLE dbo.bronze_edgar_raw (
            id INT IDENTITY(1,1) PRIMARY KEY,
            company_name NVARCHAR(100),
            cik NVARCHAR(20),
            metric_name NVARCHAR(100),
            metric_label NVARCHAR(100),
            concept NVARCHAR(200),
            period_end DATE,
            period_start DATE,
            form NVARCHAR(20),
            filed DATE,
            value FLOAT,
            unit NVARCHAR(20),
            ingestion_date DATE,
            ingestion_timestamp DATETIME DEFAULT GETDATE()
        )
    """)
    conn.commit()


    # Clear today's data before reinserting to prevent duplicates
    cursor.execute("DELETE FROM dbo.bronze_edgar_raw WHERE ingestion_date = %s", (datetime.utcnow().date(),))
    conn.commit()
    logging.info("Cleared today's existing rows")

    
    for company_name, cik in COMPANIES.items():
        try:
            blob_path = f"{ingestion_date}/{company_name}.json"
            blob_client = container.get_blob_client(blob_path)
            raw_json = json.loads(blob_client.download_blob().readall())

            entity_cik = raw_json.get("cik", cik)
            facts = raw_json.get("facts", {})
            us_gaap = facts.get("us-gaap", {})

            rows_inserted = 0

            for concept, label in METRICS.items():
                if concept not in us_gaap:
                    continue

                concept_data = us_gaap[concept]
                units = concept_data.get("units", {})
                entries = units.get("USD", units.get("shares", units.get("USD/shares", [])))

                for entry in entries:
                    form = entry.get("form", "")
                    if form not in ("10-K", "10-Q"):
                        continue

                    cursor.execute("""
                        INSERT INTO dbo.bronze_edgar_raw
                        (company_name, cik, metric_name, metric_label, concept,
                         period_end, period_start, form, filed, value, unit, ingestion_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        company_name,
                        str(entity_cik),
                        label,
                        concept_data.get("label", concept),
                        concept,
                        entry.get("end"),
                        entry.get("start"),
                        form,
                        entry.get("filed"),
                        entry.get("val"),
                        list(units.keys())[0],
                        datetime.utcnow().date()
                    ))
                    rows_inserted += 1

            conn.commit()
            logging.info(f"  {company_name}: {rows_inserted} rows inserted")

        except Exception as e:
            logging.error(f"  ERROR on {company_name}: {str(e)}")

    cursor.close()
    conn.close()
    logging.info("Transform complete")

