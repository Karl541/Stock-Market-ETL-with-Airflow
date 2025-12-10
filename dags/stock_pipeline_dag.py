import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from stock_etl import default_conn_kwargs, fetch_stock_rows, insert_rows, process_rows


def fetch_stock_data(**context):
    """Fetch stock rows and push to XCom."""
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY") or ""
    symbol = os.getenv("STOCK_SYMBOL", "IBM")
    rows = fetch_stock_rows(symbol, api_key)
    context["ti"].xcom_push(key="stock_rows", value=rows)
    return f"Pushed {len(rows)} rows for {symbol}"


def process_stock_data(**context):
    """Process raw rows and push cleaned list to XCom."""
    rows = context["ti"].xcom_pull(task_ids="fetch_stock_data", key="stock_rows")
    if not rows:
        print("No raw stock data found in XCom — skipping processing.")
        return []

    cleaned_rows = process_rows(rows)
    context["ti"].xcom_push(key="clean_rows", value=cleaned_rows)
    return f"Prepared {len(cleaned_rows)} rows for storage"


def store_stock_data(**context):
    """Store processed rows into PostgreSQL."""
    rows = context["ti"].xcom_pull(task_ids="process_stock_data", key="clean_rows")
    if not rows:
        print("No processed stock data found in XCom — skipping DB insert.")
        return "No rows to insert"

    inserted = insert_rows(rows, default_conn_kwargs())
    return f"Inserted {inserted} rows into PostgreSQL"


default_args = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(seconds=20),
}

with DAG(
    dag_id="stock_market_pipeline",
    description="Daily ETL pipeline for IBM stock prices",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["stocks", "postgres", "ETL"],
):
    fetch_task = PythonOperator(
        task_id="fetch_stock_data",
        python_callable=fetch_stock_data,
    )

    process_task = PythonOperator(
        task_id="process_stock_data",
        python_callable=process_stock_data,
    )

    store_task = PythonOperator(
        task_id="store_stock_data",
        python_callable=store_stock_data,
    )

    _ = fetch_task >> process_task >> store_task
