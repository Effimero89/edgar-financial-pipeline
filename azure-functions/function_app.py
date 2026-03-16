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

COMPANIES_BATCH_1 = {
    "Apple": "0000320193",
    "Microsoft": "0000789019",
    "Amazon": "0001018724",
    "JPMorgan": "0000019617",
    "Johnson & Johnson": "0000200406",
    "Walmart": "0000104169",
    "Nike": "0000320187",
    "Coca-Cola": "0000021344",
    "McDonalds": "0000063908",
    "Visa": "0001403161",
    "Nvidia": "0001045810",
    "Alphabet": "0001652044",
    "Meta Platforms": "0001326801",
    "Broadcom": "0001730168",
    "Tesla": "0001318605",
    "Eli Lilly": "0000059478",
    "ExxonMobil": "0000034088",
    "Mastercard": "0001141391",
    "Costco": "0000909832",
    "Oracle": "0001341439",
    "Netflix": "0001065280",
    "AbbVie": "0001551152",
    "Chevron": "0000093410",
    "Palantir": "0001321655",
    "Procter & Gamble": "0000080424",
    "Home Depot": "0000354950",
    "Bank of America": "0000070858",
    "GE Aerospace": "0000040545",
    "Caterpillar": "0000018230",
    "AMD": "0000002488",
    "Cisco": "0000858877",
    "Merck": "0000310158",
}

COMPANIES_BATCH_2 = {
    "RTX Corporation": "0000101829",
    "Philip Morris": "0001413329",
    "UnitedHealth": "0000731766",
    "Applied Materials": "0000006951",
    "Morgan Stanley": "0000895421",
    "Lowes": "0000060667",
    "Goldman Sachs": "0000886982",
    "BlackRock": "0001364742",
    "Intuit": "0000896878",
    "T-Mobile": "0001283699",
    "ServiceNow": "0001373715",
    "Salesforce": "0001108524",
    "Qualcomm": "0000804328",
    "Amgen": "0000318154",
    "Honeywell": "0000773840",
    "SP Global": "0000064040",
    "Charles Schwab": "0000316709",
    "Booking Holdings": "0001075531",
    "Pepsico": "0000077476",
    "Thermo Fisher": "0000097745",
    "Danaher": "0000313616",
    "Adobe": "0000796343",
    "Texas Instruments": "0000097476",
    "Gambling.com": "0001839799",
    "Enovix": "0001828318",
    "AST SpaceMobile": "0001780312",
    "Rocket Lab": "0001819994",
    "Intuitive Machines": "0001844452",
    "Planet Labs": "0001836833",
    "Redwire": "0001819810",
    "Red Cat Holdings": "0000748268",
}

COMPANIES_ALL = {**COMPANIES_BATCH_1, **COMPANIES_BATCH_2}

HEADERS = {"User-Agent": "Tyler Mistretta effimero89@gmail.com"}
BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts/"

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


def _run_ingest(companies: dict) -> None:
    connection_string = os.environ["ADLS_CONNECTION_STRING"]
    blob_service = BlobServiceClient.from_connection_string(connection_string)
    container = blob_service.get_container_client("bronze")
    ingestion_date = datetime.utcnow().strftime("%Y/%m/%d")
    success_count = 0
    error_count = 0

    for company_name, cik in companies.items():
        try:
            logging.info(f"Pulling {company_name}...")
            url = f"{BASE_URL}CIK{cik}.json"
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            raw_json = response.json()

            blob_path = f"{ingestion_date}/{company_name}.json"
            blob_client = container.get_blob_client(blob_path)
            blob_client.upload_blob(json.dumps(raw_json), overwrite=True)

            logging.info(f"  Saved to bronze/{blob_path}")
            success_count += 1
            time.sleep(0.5)

        except Exception as e:
            logging.error(f"  ERROR on {company_name}: {str(e)}")
            error_count += 1

    logging.info(f"Ingest complete. Success: {success_count}, Errors: {error_count}")


def _run_transform(companies: dict) -> None:
    connection_string = os.environ["ADLS_CONNECTION_STRING"]
    blob_service = BlobServiceClient.from_connection_string(connection_string)
    container = blob_service.get_container_client("bronze")
    ingestion_date = datetime.utcnow().strftime("%Y/%m/%d")

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

    for company_name, cik in companies.items():
        try:
            cursor.execute(
                "DELETE FROM dbo.bronze_edgar_raw WHERE ingestion_date = %s AND company_name = %s",
                (datetime.utcnow().date(), company_name)
            )
            conn.commit()

            blob_path = f"{ingestion_date}/{company_name}.json"
            blob_client = container.get_blob_client(blob_path)
            raw_json = json.loads(blob_client.download_blob().readall())

            entity_cik = raw_json.get("cik", cik)
            facts = raw_json.get("facts", {})
            us_gaap = facts.get("us-gaap", {})

            rows = []

            for concept, label in METRICS.items():
                if concept not in us_gaap:
                    continue

                concept_data = us_gaap[concept]
                units = concept_data.get("units", {})
                entries = units.get("USD", units.get("shares", units.get("USD/shares", [])))
                unit_key = list(units.keys())[0] if units else "USD"

                for entry in entries:
                    form = entry.get("form", "")
                    if form not in ("10-K", "10-Q"):
                        continue

                    rows.append((
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
                        unit_key,
                        datetime.utcnow().date()
                    ))

            if rows:
                cursor.executemany("""
                    INSERT INTO dbo.bronze_edgar_raw
                    (company_name, cik, metric_name, metric_label, concept,
                     period_end, period_start, form, filed, value, unit, ingestion_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, rows)
                conn.commit()

            logging.info(f"  {company_name}: {len(rows)} rows inserted")

        except Exception as e:
            logging.error(f"  ERROR on {company_name}: {str(e)}")
        
    # write bronze metadata
    cursor.execute("""
          INSERT INTO dbo.pipeline_metadata 
              (layer, last_refresh, row_count, records_added, status, duration_sec, source, triggered_by, error_message, environment)
          SELECT 'bronze', GETUTCDATE(), COUNT(*), NULL, 'success', NULL, 'azure_function', 'timer_trigger', NULL, 'dev'
          FROM dbo.bronze_edgar_raw
          WHERE ingestion_date = %s
      """, (datetime.utcnow().date(),))
    conn.commit()

    cursor.close()
    conn.close()
    logging.info("Transform complete")

    cursor.close()
    conn.close()
    logging.info("Transform complete")


@app.timer_trigger(
    schedule="0 0 8 * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=False
)
def edgar_ingest_batch1(myTimer: func.TimerRequest) -> None:
    logging.info(f"edgar_ingest_batch1 started at {datetime.utcnow()}")
    _run_ingest(COMPANIES_BATCH_1)


@app.timer_trigger(
    schedule="0 10 8 * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=False
)
def edgar_ingest_batch2(myTimer: func.TimerRequest) -> None:
    logging.info(f"edgar_ingest_batch2 started at {datetime.utcnow()}")
    _run_ingest(COMPANIES_BATCH_2)


@app.timer_trigger(
    schedule="0 20 9 * * *",
    arg_name="transformTimer",
    run_on_startup=False,
    use_monitor=False
)
def edgar_transform_batch1(transformTimer: func.TimerRequest) -> None:
    logging.info(f"edgar_transform_batch1 started at {datetime.utcnow()}")
    _run_transform(COMPANIES_BATCH_1)


@app.timer_trigger(
    schedule="0 30 9 * * *",
    arg_name="transformTimer",
    run_on_startup=False,
    use_monitor=False
)
def edgar_transform_batch2(transformTimer: func.TimerRequest) -> None:
    logging.info(f"edgar_transform_batch2 started at {datetime.utcnow()}")
    _run_transform(COMPANIES_BATCH_2)