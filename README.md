# Stock Market ETL with Airflow (Docker Compose)

This repo runs a simple daily ETL that fetches stock prices from Alpha Vantage, processes them, and stores them in PostgreSQL using Airflow. Everything runs in Docker via `docker-compose`.

## What’s here
- `docker-compose.yaml` — spins up Airflow (webserver/scheduler/worker), Postgres, and Redis.
- `dags/stock_pipeline_dag.py` — the Airflow DAG (`stock_market_pipeline`) that orchestrates fetch → process → store.
- `dags/stock_etl.py` — shared ETL helpers: call Alpha Vantage, clean rows, and insert into Postgres.

## Prereqs
- Docker Desktop (with Compose) running.
- An Alpha Vantage API key.

## Setup
1) Clone or copy the repo.
2) In the project root, create a `.env` file (Compose loads it) with at least:
```
ALPHA_VANTAGE_API_KEY=your_api_key_here
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=airflow
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
STOCK_SYMBOL=IBM
```
   - Change Postgres creds if you want, but keep them consistent with `docker-compose.yaml`.
   - `STOCK_SYMBOL` is the ticker to fetch; default is `IBM`.

## Run it
From the project root:
- Windows PowerShell or macOS/Linux: `docker-compose up --build`

Give Airflow a minute to initialize. Then open http://localhost:8080 (default user/pass: `airflow` / `airflow`).

## Trigger the pipeline
- In Airflow UI, enable and trigger `stock_market_pipeline`, or wait for the daily schedule.
- Tasks:
  - `fetch_stock_data` → pulls Alpha Vantage JSON.
  - `process_stock_data` → cleans/sorts rows.
  - `store_stock_data` → creates the table if needed and upserts into Postgres.

## Where data lives
- Postgres runs in the `postgres` service. Table: `stock_data` with unique `(symbol, date)`.
- Compose defines a volume for Postgres data (`postgres-db-volume`).

## Troubleshooting
- Missing API key: set `ALPHA_VANTAGE_API_KEY` in `.env`.
- Port conflicts: adjust ports in `docker-compose.yaml` (Postgres 5432, Airflow web 8080).
- Clean logs: remove the `logs/` folder if it grows too large.

