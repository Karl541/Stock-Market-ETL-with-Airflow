import os
from typing import Dict, Iterable, List

import psycopg2
import requests


class DataFetchError(Exception):
    """Raised when stock data cannot be fetched or parsed."""


def fetch_stock_rows(symbol: str, api_key: str, *, timeout: int = 15) -> List[Dict]:
    """
    Fetch raw daily time-series data for the symbol.
    Raises DataFetchError for network or format issues.
    """
    if not api_key:
        raise DataFetchError("Missing API key. Set ALPHA_VANTAGE_API_KEY in the environment.")

    url = (
        "https://www.alphavantage.co/query"
        f"?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={api_key}"
    )

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise DataFetchError(f"Network failure while fetching stock data: {exc}") from exc

    time_series = data.get("Time Series (Daily)")
    if not time_series:
        raise DataFetchError(f"Unexpected API response shape: {data}")

    meta = data.get("Meta Data", {})
    reported_symbol = meta.get("2. Symbol", symbol)

    rows: List[Dict] = []
    for date_str, values in time_series.items():
        try:
            rows.append(
                {
                    "symbol": reported_symbol,
                    "date": date_str,
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                    "volume": int(values["5. volume"]),
                }
            )
        except (KeyError, ValueError, TypeError) as exc:
            # Skip malformed rows but continue the pipeline
            print(f"Skipping malformed data for {reported_symbol} on {date_str}: {exc}")
            continue

    if not rows:
        raise DataFetchError("API returned no valid rows to process.")

    return rows


def process_rows(rows: Iterable[Dict]) -> List[Dict]:
    """Basic processing: drop empties and sort deterministically by date."""
    cleaned = [r for r in rows if r]
    cleaned = sorted(cleaned, key=lambda r: r["date"])
    return cleaned


def insert_rows(rows: Iterable[Dict], conn_kwargs: Dict) -> int:
    """Insert rows into PostgreSQL; returns inserted (or deduped) count."""
    rows = list(rows)
    if not rows:
        return 0

    conn = psycopg2.connect(**conn_kwargs)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_data (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(10),
            date DATE,
            open FLOAT,
            high FLOAT,
            low FLOAT,
            close FLOAT,
            volume BIGINT,
            UNIQUE(symbol, date)
        );
    """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS stock_data_symbol_date_idx
        ON stock_data(symbol, date);
    """
    )

    for row in rows:
        cur.execute(
            """
            INSERT INTO stock_data (symbol, date, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, date) DO NOTHING;
        """,
            (
                row["symbol"],
                row["date"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
            ),
        )

    conn.commit()
    cur.close()
    conn.close()
    return len(rows)


def default_conn_kwargs() -> Dict:
    """Build psycopg2 connection kwargs from environment with safe defaults."""
    return {
        "host": os.getenv("POSTGRES_HOST", "postgres"),
        "user": os.getenv("POSTGRES_USER", "airflow"),
        "password": os.getenv("POSTGRES_PASSWORD", "airflow"),
        "dbname": os.getenv("POSTGRES_DB", "airflow"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
    }

